#
# Copyright 2015 Quantopian, Inc.
# Modifications Copyright 2018 Alpaca
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import warnings
import pytz
import numpy as np
import pandas as pd
from datetime import tzinfo
from itertools import chain
from contextlib import ExitStack
from copy import copy
import importlib
from trading_calendars import get_calendar

import pylivetrader.protocol as proto
from pylivetrader.assets import AssetFinder, Asset
from pylivetrader.data.bardata import handle_non_market_minutes
from pylivetrader.data.data_portal import DataPortal
from pylivetrader.executor.executor import AlgorithmExecutor
from pylivetrader.errors import (
    APINotSupported, CannotOrderDelistedAsset, UnsupportedOrderParameters,
    ScheduleFunctionInvalidCalendar, OrderDuringInitialize,
    RegisterAccountControlPostInit, RegisterTradingControlPostInit,
    OrderInBeforeTradingStart, HistoryInInitialize,
)
from pylivetrader.finance.execution import (
    MarketOrder, LimitOrder, StopLimitOrder, StopOrder
)
from pylivetrader.finance.controls import (
    LongOnly,
    MaxOrderCount,
    MaxOrderSize,
    MaxPositionSize,
    MaxLeverage,
    RestrictedListOrder
)
from pylivetrader.finance.asset_restrictions import (
    Restrictions,
    NoRestrictions,
    StaticRestrictions,
    SecurityListRestrictions,
)

from pylivetrader.misc.security_list import SecurityList
from pylivetrader.misc import events
from pylivetrader.misc.events import (
    EventManager,
    make_eventrule,
    date_rules,
    time_rules,
    calendars,
    AfterOpen,
    BeforeClose
)
from pylivetrader.misc.math_utils import round_if_near_integer, tolerant_equals
from pylivetrader.misc.api_context import (
    api_method,
    LiveTraderAPI,
    require_initialized,
    disallowed_in_before_trading_start,
)
from pylivetrader.misc.pd_utils import normalize_date
from pylivetrader.misc.preprocess import preprocess
from pylivetrader.misc.input_validation import (
    coerce_string,
    ensure_upper_case,
    expect_types,
    expect_dtypes,
    optional,
)
from pylivetrader.statestore import StateStore, FileStore, RedisStore

from logbook import Logger, lookup_level


log = Logger('Algorithm')


class Algorithm(object):
    """Provides algorithm compatible with zipline.
    """

    def __setattr__(self, name, value):
        # Reject names that overlap with API method names
        if hasattr(self, 'api_methods') and name in self.api_methods:
            raise AttributeError(
                'Cannot set {} on context object as it is the name of '
                'an API method.'.format(name)
            )
        else:
            object.__setattr__(self, name, value)

    def __init__(self, *args, **kwargs):
        '''
        data_frequency: 'minute' or 'daily'
        algoname: str, defaults to 'algo'
        backend: str or Backend instance, defaults to 'alpaca'
                 (str is either backend module name under
                  'pylivetrader.backend', or global import path)
        trading_calendar: pd.DateIndex for trading calendar
        initialize: initialize function
        handle_data: handle_data function
        before_trading_start: before_trading_start function
        log_level: 'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'
        storage_engine: 'file', 'redis'
        '''
        log.level = lookup_level(kwargs.pop('log_level', 'INFO'))
        self._recorded_vars = {}

        self.data_frequency = kwargs.pop('data_frequency', 'minute')
        assert self.data_frequency in ('minute', 'daily')

        self._algoname = kwargs.pop('algoname', 'algo')

        self.quantopian_compatible = kwargs.pop('quantopian_compatible', True)

        storage_engine = kwargs.pop('storage_engine', 'file')
        if storage_engine == 'redis':
            storage_engine = RedisStore()
        else:
            storage_engine = FileStore(
                kwargs.pop('statefile', None) or
                '{}-state.pkl'.format(self._algoname)
            )
        self._state_store = StateStore(storage_engine=storage_engine)

        self._pipelines = {}

        backend_param = kwargs.pop('backend', 'alpaca')
        if not isinstance(backend_param, str):
            self._backend = backend_param
            self._backend_name = backend_param.__class__.__name__
        else:
            self._backend_name = backend_param
            try:
                # First, tries to import official backend packages
                backendmod = importlib.import_module(
                    'pylivetrader.backend.{}'.format(self._backend_name))
            except ImportError:
                # Then if failes, tries to find pkg in global package
                # namespace.
                try:
                    backendmod = importlib.import_module(
                        self._backend_name)
                except ImportError:
                    raise RuntimeError(
                        "Could not find backend package `{}`.".format(
                            self._backend_name))

            backend_options = kwargs.pop('backend_options', None) or {}
            self._backend = backendmod.Backend(**backend_options)

        self.asset_finder = AssetFinder(self._backend)

        self.trading_calendar = kwargs.pop(
            'trading_calendar', get_calendar('NYSE'))

        self.data_portal = DataPortal(
            self._backend,
            self.asset_finder,
            self.trading_calendar,
            self.quantopian_compatible
        )

        self.event_manager = EventManager()

        self.trading_controls = []

        self.account_controls = []

        self.restrictions = NoRestrictions()

        self._initialize = kwargs.pop('initialize', noop)
        self._handle_data = kwargs.pop('handle_data', noop)
        self._before_trading_start = kwargs.pop('before_trading_start', noop)

        self.event_manager.add_event(
            events.Event(
                events.Always(),
                # We pass handle_data.__func__ to get the unbound method.
                self.handle_data.__func__,
            ),
            prepend=True,
        )

        self._account_needs_update = True
        self._portfolio_needs_update = True

        self._in_before_trading_start = False

        self._assets_from_source = []

        self._context_persistence_excludes = []

        self._max_shares = int(1e+11)

        self.initialized = False

        self.api_methods = [func for func in dir(Algorithm) if callable(
            getattr(Algorithm, func)
        )]

    def initialize(self, *args, **kwargs):
        self._context_persistence_excludes = (
            list(self.__dict__.keys()) + ['executor'])
        self._state_store.load(self, self._algoname)

        self._backend.initialize_data(self)

        with LiveTraderAPI(self):
            self._initialize(self, *args, **kwargs)
            self._state_store.save(
                self, self._algoname, self._context_persistence_excludes)

        self.initialized = True

    def handle_data(self, data):
        if self._handle_data:
            self._handle_data(self, data)
            self._state_store.save(
                self, self._algoname, self._context_persistence_excludes)

    def before_trading_start(self, data):
        if self._before_trading_start is None:
            return

        self._in_before_trading_start = True

        with handle_non_market_minutes(data) if \
                self.data_frequency == "minute" else ExitStack():
            self._before_trading_start(self, data)
            self._state_store.save(
                self, self._algoname, self._context_persistence_excludes)

        self._in_before_trading_start = False

    def run(self, retry=True):

        log.info(
            "livetrader start running with "
            "backend = {} "
            "data-frequency = {}".format(
                self._backend_name, self.data_frequency)
        )

        # for compatibility with zipline to provide history api
        self._assets_from_source = \
            self.asset_finder.retrieve_all(self.asset_finder.sids)

        if not self.initialized:
            self.initialize()

        self.executor = AlgorithmExecutor(
            self,
            self.data_portal,
        )

        return self.executor.run(retry=retry)

    @api_method
    def get_environment(self, field='platform'):
        raise APINotSupported

    @api_method
    def fetch_csv(self,
                  url,
                  pre_func=None,
                  post_func=None,
                  date_column='date',
                  date_format=None,
                  timezone=pytz.utc.zone,
                  symbol=None,
                  mask=True,
                  symbol_column=None,
                  special_params_checker=None,
                  **kwargs):
        raise APINotSupported

    @api_method
    @disallowed_in_before_trading_start(OrderInBeforeTradingStart())
    def order(
            self,
            asset,
            amount,
            limit_price=None,
            stop_price=None,
            style=None):

        if not self._can_order_asset(asset):
            return None

        amount, style = self._calculate_order(
            asset, amount, limit_price, stop_price, style)

        if amount == 0:
            return None

        if amount > self._max_shares:
            # Arbitrary limit of 100 billion (US) shares will never be
            # exceeded except by a buggy algorithm.
            raise OverflowError("Can't order more than %d shares" %
                                self._max_shares)

        o = self._backend.order(
            asset, amount, style, self.quantopian_compatible
        )
        if o:
            return o.id

    @api_method
    def add_event(self, rule=None, callback=None):
        self.event_manager.add_event(
            events.Event(rule, callback),
        )

    @api_method
    def schedule_function(self,
                          func,
                          date_rule=None,
                          time_rule=None,
                          half_days=True,
                          calendar=None):
        """Schedules a function to be called according to some timed rules.

        Parameters
        ----------
        func : callable[(context, data) -> None]
            The function to execute when the rule is triggered.
        date_rule : EventRule, optional
            The rule for the dates to execute this function.
        time_rule : EventRule, optional
            The rule for the times to execute this function.
        half_days : bool, optional
            Should this rule fire on half days?
        calendar : Sentinel, optional
            Calendar used to reconcile date and time rules.

        See Also
        --------
        :class:`zipline.api.date_rules`
        :class:`zipline.api.time_rules` sta
        """

        # When the user calls schedule_function(func, <time_rule>), assume that
        # the user meant to specify a time rule but no date rule, instead of
        # a date rule and no time rule as the signature suggests
        if isinstance(date_rule, (AfterOpen, BeforeClose)) and not time_rule:
            warnings.warn('Got a time rule for the second positional argument '
                          'date_rule. You should use keyword argument '
                          'time_rule= when calling schedule_function without '
                          'specifying a date_rule', stacklevel=3)

        date_rule = date_rule or date_rules.every_day()
        time_rule = ((time_rule or time_rules.every_minute())
                     if self.data_frequency == 'minute' else
                     # If we are in daily mode the time_rule is ignored.
                     time_rules.every_minute())

        # Check the type of the algorithm's schedule before pulling calendar
        # Note that the ExchangeTradingSchedule is currently the only
        # TradingSchedule class, so this is unlikely to be hit
        if calendar is None:
            cal = self.trading_calendar
        elif calendar is calendars.US_EQUITIES:
            cal = get_calendar('NYSE')
        elif calendar is calendars.US_FUTURES:
            cal = get_calendar('us_futures')
        else:
            raise ScheduleFunctionInvalidCalendar(
                given_calendar=calendar,
                allowed_calendars=(
                    '[calendars.US_EQUITIES, calendars.US_FUTURES]'
                ),
            )

        self.add_event(
            make_eventrule(date_rule, time_rule, cal, half_days),
            func,
        )

    @api_method
    def record(self, *args, **kwargs):
        """Track and record values each day.

        Parameters
        ----------
        **kwargs
            The names and values to record.

        Notes
        -----
        These values will appear in the performance packets and the performance
        dataframe passed to ``analyze`` and returned from
        :func:`~zipline.run_algorithm`.
        """
        # Make 2 objects both referencing the same iterator
        args = [iter(args)] * 2

        # Zip generates list entries by calling `next` on each iterator it
        # receives.  In this case the two iterators are the same object, so the
        # call to next on args[0] will also advance args[1], resulting in zip
        # returning (a,b) (c,d) (e,f) rather than (a,a) (b,b) (c,c) etc.
        positionals = zip(*args)
        for name, value in chain(positionals, kwargs.items()):
            self._recorded_vars[name] = value

    @api_method
    def set_benchmark(self, benchmark):
        '''Just do nothing for compatibility.'''
        pass

    @api_method
    @preprocess(symbol=ensure_upper_case)
    def symbol(self, symbol):
        '''Lookup equity by symbol.

        Parameters:
            symbol (string): The ticker symbol for the asset.

        Returns:
            equity (Equity): The equity object lookuped by the ``symbol``.

        Raises:
            AssetNotFound: When could not resolve the ``Asset`` by ``symbol``.
        '''
        return self.asset_finder.lookup_symbol(symbol, as_of_date=None)

    @api_method
    def continuous_future(self, *args, **kwargs):
        raise APINotSupported

    @api_method
    def symbols(self, *args, **kwargs):
        '''Lookup equities by symbol.

        Parameters:
            args (iterable[str]): List of ticker symbols for the asset.

        Returns:
            equities (List[Equity]): The equity lookuped by the ``symbol``.

        Raises:
            AssetNotFound: When could not resolve the ``Asset`` by ``symbol``.
        '''
        return [self.symbol(idendifier, **kwargs) for idendifier in args]

    @api_method
    def sid(self, sid):
        '''Lookup equity by asset unique identifier

        Parameters:
            sid: asset unique identifier.

        Returns:
            equity (Equity): The equity object lookuped by the ``sid``.

        Raises:
            AssetNotFound: When could not resolve the ``Asset`` by ``sid``.
        '''
        return self.asset_finder.retrieve_asset(sid)

    @api_method
    def future_symbol(self, symbol):
        raise APINotSupported

    @api_method
    def batch_order(self, order_arg_list):
        return [self.order(*order_args) for order_args in order_arg_list]

    @api_method
    @disallowed_in_before_trading_start(OrderInBeforeTradingStart())
    def order_value(
            self,
            asset,
            value,
            limit_price=None,
            stop_price=None,
            style=None):
        if not self._can_order_asset(asset):
            return None

        amount = self._calculate_order_value_amount(asset, value)
        return self.order(asset, amount,
                          limit_price=limit_price,
                          stop_price=stop_price,
                          style=style)

    @property
    def recorded_vars(self):
        return copy(self._recorded_vars)

    @property
    def portfolio(self):
        if self._portfolio_needs_update:
            self._portfolio = self._backend.portfolio
            self._portfolio_needs_update = False
        return self._portfolio

    @property
    def account(self):
        if self._account_needs_update:
            self._account = self._backend.account
            self._account_needs_update = False
        return self._account

    def on_dt_changed(self, dt):
        self._portfolio_needs_update = True
        self._account_needs_update = True
        self.datetime = dt

    @api_method
    @preprocess(tz=coerce_string(pytz.timezone))
    @expect_types(tz=optional(tzinfo))
    def get_datetime(self, tz=None):
        dt = self.datetime
        assert dt.tzinfo == pytz.utc, "Algorithm should have a utc datetime"
        if tz is not None:
            dt = dt.astimezone(tz)
        return dt

    @api_method
    def set_slippage(self, **kwargs):
        '''Just do nothing for compatibility.'''
        pass

    @api_method
    def set_commission(self, **kwargs):
        '''Just do nothing for compatibility.'''
        pass

    @api_method
    def set_cancel_policy(self, *args):
        '''Just do nothing for compatibility.'''
        pass

    @api_method
    def set_symbol_lookup_date(self, dt):
        '''Just do nothing for compatibility.'''
        pass

    @api_method
    def order_percent(
            self,
            asset,
            percent,
            limit_price=None,
            stop_price=None,
            style=None):
        if not self._can_order_asset(asset):
            return None

        amount = self._calculate_order_percent_amount(asset, percent)
        return self.order(asset, amount,
                          limit_price=limit_price,
                          stop_price=stop_price,
                          style=style)

    @api_method
    def order_target(
            self,
            asset,
            target,
            limit_price=None,
            stop_price=None,
            style=None):
        if not self._can_order_asset(asset):
            return None

        amount = self._calculate_order_target_amount(asset, target)
        return self.order(asset, amount,
                          limit_price=limit_price,
                          stop_price=stop_price,
                          style=style)

    @api_method
    def order_target_value(
            self,
            asset,
            target,
            limit_price=None,
            stop_price=None,
            style=None):
        if not self._can_order_asset(asset):
            return None

        target_amount = self._calculate_order_value_amount(asset, target)
        amount = self._calculate_order_target_amount(asset, target_amount)
        return self.order(asset, amount,
                          limit_price=limit_price,
                          stop_price=stop_price,
                          style=style)

    @api_method
    def order_target_percent(
            self,
            asset,
            target,
            limit_price=None,
            stop_price=None,
            style=None):
        if not self._can_order_asset(asset):
            return None

        amount = self._calculate_order_target_percent_amount(asset, target)
        return self.order(asset, amount,
                          limit_price=limit_price,
                          stop_price=stop_price,
                          style=style)

    @api_method
    @expect_types(share_counts=pd.Series)
    @expect_dtypes(share_counts=np.dtype('float64'))
    def batch_market_order(self, share_counts):
        style = MarketOrder()
        order_args = [
            (asset, amount, style)
            for (asset, amount) in share_counts.items()
            if amount
        ]
        return self._backend.batch_order(order_args)

    @api_method
    def get_open_orders(self, asset=None):
        '''
        If asset is unspecified or None, returns a dictionary keyed by
        asset ID. The dictionary contains a list of orders for each ID,
        oldest first. If an asset is specified, returns a list of open
        orders for that asset, oldest first.
        '''
        return self.get_all_orders(asset=asset, status='open')

    @api_method
    def get_recent_orders(self, days_back=2):
        '''
        Returns all orders from the past n days.
        '''
        return self.get_all_orders(days_back=days_back)

    @api_method
    def get_all_orders(
            self,
            asset=None,
            before=None,
            status='all',
            days_back=None):
        '''
        If asset is unspecified or None, returns a dictionary keyed by
        asset ID. The dictionary contains a list of orders for each ID,
        oldest first. If an asset is specified, returns a list of open
        orders for that asset, oldest first. Orders submitted after
        before will not be returned. If provided, only orders of type
        status ('closed' or 'open') will be returned.
        '''
        orders = self._backend.all_orders(before, status, days_back)

        omap = {}
        sorted_orders = sorted([
            o for o in orders.values()
        ], key=lambda o: o.dt)
        for order in sorted_orders:
            key = order.asset
            if key not in omap:
                omap[key] = []
            omap[key].append(order.to_api_obj())

        if asset is None:
            return omap

        return omap.get(asset, [])

    @api_method
    def get_order(self, order_id):
        return self._backend.get_order(order_id).to_api_obj()

    @api_method
    def cancel_order(self, order_param):
        order_id = order_param
        if isinstance(order_param, proto.Order):
            order_id = order_param.id
        self._backend.cancel_order(order_id)

    @api_method
    @require_initialized(HistoryInInitialize())
    def history(self, bar_count, frequency, field, ffill=True):
        """DEPRECATED: use ``data.history`` instead.
        """

        return self.get_history_window(
            bar_count,
            frequency,
            self._calculate_universe(),
            field,
            ffill,
        )

    def get_history_window(self, bar_count, frequency, assets, field, ffill):
        return self.data_portal.get_history_window(
            assets,
            self.datetime,
            bar_count,
            frequency,
            field,
            self.data_frequency,
            ffill,
        )

    def _calculate_order(self, asset, amount,
                         limit_price=None, stop_price=None, style=None):
        amount = self.round_order(amount)

        # Raises a ZiplineError if invalid parameters are detected.
        self.validate_order_params(asset,
                                   amount,
                                   limit_price,
                                   stop_price,
                                   style)

        # Convert deprecated limit_price and stop_price parameters to use
        # ExecutionStyle objects.
        style = self.__convert_order_params_for_blotter(limit_price,
                                                        stop_price,
                                                        style)
        return amount, style

    def validate_order_params(self,
                              asset,
                              amount,
                              limit_price,
                              stop_price,
                              style):
        """
        Helper method for validating parameters to the order API function.

        Raises an UnsupportedOrderParameters if invalid arguments are found.
        """

        if not self.initialized:
            raise OrderDuringInitialize(
                msg="order() can only be called from within handle_data()"
            )

        if style:
            if limit_price:
                raise UnsupportedOrderParameters(
                    msg="Passing both limit_price and style is not supported."
                )

            if stop_price:
                raise UnsupportedOrderParameters(
                    msg="Passing both stop_price and style is not supported."
                )

        for control in self.trading_controls:
            control.validate(asset,
                             amount,
                             self.portfolio,
                             self.get_datetime(),
                             self.executor.current_data)

    @staticmethod
    def round_order(amount):
        """
        Convert number of shares to an integer.

        By default, truncates to the integer share count that's either within
        .0001 of amount or closer to zero.

        E.g. 3.9999 -> 4.0; 5.5 -> 5.0; -5.5 -> -5.0
        """
        return int(round_if_near_integer(amount))

    @staticmethod
    def __convert_order_params_for_blotter(limit_price, stop_price, style):
        """
        Helper method for converting deprecated limit_price and stop_price
        arguments into ExecutionStyle instances.

        This function assumes that either style == None or (limit_price,
        stop_price) == (None, None).
        """
        if style:
            assert (limit_price, stop_price) == (None, None)
            return style
        if limit_price and stop_price:
            return StopLimitOrder(limit_price, stop_price)
        if limit_price:
            return LimitOrder(limit_price)
        if stop_price:
            return StopOrder(stop_price)
        else:
            return MarketOrder()

    def _calculate_universe(self):
        # this exists to provide backwards compatibility for older,
        # deprecated APIs, particularly around the iterability of
        # BarData (ie, 'for sid in data`).

        # our universe is all the assets passed into `run`.
        return self._assets_from_source

    def _calculate_order_value_amount(self, asset, value):
        """
        Calculates how many shares/contracts to order based on the type of
        asset being ordered.
        """
        if not self.executor.current_data.can_trade(asset):
            raise CannotOrderDelistedAsset(
                msg="Cannot order {0}, as it not tradable".format(asset.symbol)
            )

        last_price = \
            self.executor.current_data.current(asset, "price")

        if np.isnan(last_price):
            raise CannotOrderDelistedAsset(
                msg="Cannot order {0} on {1} as there is no last "
                    "price for the security.".format(asset.symbol,
                                                     self.datetime)
            )

        if tolerant_equals(last_price, 0):
            zero_message = "Price of 0 for {psid}; can't infer value".format(
                psid=asset
            )
            log.debug(zero_message)
            # Don't place any order
            return 0

        return value / last_price

    def _calculate_order_percent_amount(self, asset, percent):
        value = self.portfolio.portfolio_value * percent
        return self._calculate_order_value_amount(asset, value)

    def _calculate_order_target_amount(self, asset, target):
        if asset in self.portfolio.positions:
            current_position = self.portfolio.positions[asset].amount
            target -= current_position

        return target

    def _calculate_order_target_percent_amount(self, asset, target):
        target_amount = self._calculate_order_percent_amount(asset, target)
        return self._calculate_order_target_amount(asset, target_amount)

    def _can_order_asset(self, asset):

        if not isinstance(asset, Asset):
            raise UnsupportedOrderParameters(
                msg="Passing non-Asset argument to 'order()' is not supported."
                    " Use 'sid()' or 'symbol()' methods to look up an Asset."
            )

        if asset.auto_close_date:
            day = normalize_date(self.get_datetime())

            if day > min(asset.end_date, asset.auto_close_date):
                # If we are after the asset's end date or auto close date, warn
                # the user that they can't place an order for this asset, and
                # return None.
                log.warn("Cannot place order for {0}"
                         ", as it is not tradable.".format(asset.symbol))

                return False

        return True

    #
    # Account Controls
    #
    def register_account_control(self, control):
        """
        Register a new AccountControl to be checked on each bar.
        """
        if self.initialized:
            raise RegisterAccountControlPostInit()
        self.account_controls.append(control)

    def validate_account_controls(self):
        for control in self.account_controls:
            control.validate(self.portfolio,
                             self.account,
                             self.get_datetime(),
                             self.executor.current_data)

    @api_method
    def set_max_leverage(self, max_leverage):
        """Set a limit on the maximum leverage of the algorithm.

        Parameters
        ----------
        max_leverage : float
            The maximum leverage for the algorithm. If not provided there will
            be no maximum.
        """
        control = MaxLeverage(max_leverage)
        self.register_account_control(control)

    #
    # Trading Controls
    #
    def register_trading_control(self, control):
        """
        Register a new TradingControl to be checked prior to order calls.
        """
        if self.initialized:
            raise RegisterTradingControlPostInit()
        self.trading_controls.append(control)

    @api_method
    def set_max_position_size(
            self,
            asset=None,
            max_shares=None,
            max_notional=None,
            on_error='fail'):
        """Set a limit on the number of shares and/or dollar value held for the
        given sid. Limits are treated as absolute values and are enforced at
        the time that the algo attempts to place an order for sid. This means
        that it's possible to end up with more than the max number of shares
        due to splits/dividends, and more than the max notional due to price
        improvement.

        If an algorithm attempts to place an order that would result in
        increasing the absolute value of shares/dollar value exceeding one of
        these limits, raise a TradingControlException.

        Parameters
        ----------
        asset : Asset, optional
            If provided, this sets the guard only on positions in the given
            asset.
        max_shares : int, optional
            The maximum number of shares to hold for an asset.
        max_notional : float, optional
            The maximum value to hold for an asset.
        """
        control = MaxPositionSize(asset=asset,
                                  max_shares=max_shares,
                                  max_notional=max_notional,
                                  on_error=on_error)
        self.register_trading_control(control)

    @api_method
    def set_max_order_size(self,
                           asset=None,
                           max_shares=None,
                           max_notional=None,
                           on_error='fail'):
        """Set a limit on the number of shares and/or dollar value of any single
        order placed for sid.  Limits are treated as absolute values and are
        enforced at the time that the algo attempts to place an order for sid.

        If an algorithm attempts to place an order that would result in
        exceeding one of these limits, raise a TradingControlException.

        Parameters
        ----------
        asset : Asset, optional
            If provided, this sets the guard only on positions in the given
            asset.
        max_shares : int, optional
            The maximum number of shares that can be ordered at one time.
        max_notional : float, optional
            The maximum value that can be ordered at one time.
        """
        control = MaxOrderSize(asset=asset,
                               max_shares=max_shares,
                               max_notional=max_notional,
                               on_error=on_error)
        self.register_trading_control(control)

    @api_method
    def set_max_order_count(self, max_count, on_error='fail'):
        """Set a limit on the number of orders that can be placed in a single
        day.

        Parameters
        ----------
        max_count : int
            The maximum number of orders that can be placed on any single day.
        """
        control = MaxOrderCount(on_error, max_count)
        self.register_trading_control(control)

    @api_method
    def set_do_not_order_list(self, restricted_list, on_error='fail'):
        """Set a restriction on which assets can be ordered.

        Parameters
        ----------
        restricted_list : container[Asset], SecurityList
            The assets that cannot be ordered.
        """
        if isinstance(restricted_list, SecurityList):
            warnings.warn(
                "`set_do_not_order_list(security_lists.leveraged_etf_list)` "
                "is deprecated. Use `set_asset_restrictions("
                "security_lists.restrict_leveraged_etfs)` instead.",
                category=DeprecationWarning,
                stacklevel=2
            )
            restrictions = SecurityListRestrictions(restricted_list)
        else:
            warnings.warn(
                "`set_do_not_order_list(container_of_assets)` is deprecated. "
                "Create a zipline.finance.asset_restrictions."
                "StaticRestrictions object with a container of assets and use "
                "`set_asset_restrictions(StaticRestrictions("
                "container_of_assets))` instead.",
                category=DeprecationWarning,
                stacklevel=2
            )
            restrictions = StaticRestrictions(restricted_list)

        self.set_asset_restrictions(restrictions, on_error)

    @api_method
    @expect_types(
        restrictions=Restrictions,
        on_error=str,
    )
    def set_asset_restrictions(self, restrictions, on_error='fail'):
        """Set a restriction on which assets can be ordered.

        Parameters
        ----------
        restricted_list : Restrictions
            An object providing information about restricted assets.

        See Also
        --------
        zipline.finance.asset_restrictions.Restrictions
        """
        control = RestrictedListOrder(on_error, restrictions)
        self.register_trading_control(control)
        self.restrictions |= restrictions

    @api_method
    def set_long_only(self, on_error='fail'):
        """Set a rule specifying that this algorithm cannot take short
        positions.
        """
        self.register_trading_control(LongOnly(on_error))

    @api_method
    def attach_pipeline(self, pipeline, name, chunks=None):
        self._pipelines[name] = pipeline

    @api_method
    def pipeline_output(self, name):
        try:
            from pipeline_live.engine import LivePipelineEngine
        except ImportError:
            raise RuntimeError('pipeline-live is not installed')

        finder = self.asset_finder

        def list_symbols():
            return sorted([
                a.symbol for a in finder._asset_cache.values()])

        eng = LivePipelineEngine(list_symbols)
        output = eng.run_pipeline(self._pipelines[name])
        output.index = pd.Index(finder.lookup_symbols(output.index))
        return output


def noop(*args, **kwargs):
    pass
