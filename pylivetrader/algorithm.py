import pytz
from copy import copy
import importlib
from trading_calendars import get_calendar

import pylivetrader.protocol as proto
from pylivetrader.assets import AssetFinder
from pylivetrader.data.bardata import BarData
from pylivetrader.data.data_portal import DataPortal
from pylivetrader.errors import APINotSupported
from pylivetrader.finance.execution import (
    MarketOrder, LimitOrder, StopLimitOrder, StopOrder
)
from pylivetrader.misc.zipline_utils import round_if_near_integer
from pylivetrader.misc.api_context import api_method, LiveTraderAPI


def noop(*args, **kwargs):
    pass


class Algorithm:
    """Provides algorithm compatible with zipline.
    """

    def __init__(self, *args, **kwargs):
        self._recorded_vars = {}

        self._data_frequency = kwargs.pop('data_frequency', 'minute')
        assert self._data_frequency in ('minute', 'daily')

        backend = kwargs.pop('backend', 'alpaca')
        try:
            # First, tries to import official backend packages
            backendmod = importlib.import_module(
                'pylivetrader.backend.{}'.format(backend))
        except ImportError:
            # Then if failes, tries to find pkg in global package namespace.
            try:
                backendmod = importlib.import_module(backend).Backend(**options)
            except ImportError:
                raise RuntimeError(
                    "Could not find backend package `{}`.".format(backend))

        self._backend = backendmod.Backend(**kwargs.pop('backend_options', {}))

        self.asset_finder = AssetFinder(self._backend)

        self.trading_calendar = kwargs.pop('trading_calendar', get_calendar('NYSE'))

        self.data_portal = DataPortal(
            self._backend, self.asset_finder, self.trading_calendar)

        self._bardata = BarData(
            self.data_portal,
            self._data_frequency,
            self._calculated_universe,
        )

        self._initialize = kwargs.pop('initialize', noop)
        self._handle_data = kwargs.pop('handle_data', noop)
        self._before_trading_start = kwargs.pop('before_trading_start', noop)

        self._account_needs_update = True
        self._portfolio_needs_update = True

        self._assets_from_source = []


    def run(self):
        import pandas as pd
        self.on_dt_changed(pd.Timestamp.now())

        # for compatibility with zipline to provide history api
        self._assets_from_source = \
            self.asset_finder.retrieve_all(self.asset_finder.sids)

        self._initialize(self)

        self._before_trading_start(self, self._bardata)

        self._handle_data(self, self._bardata)


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
    def order(self, asset, amount, limit_price=None, stop_price=None, style=None):
        amount, style = self._calculate_order(
            asset, amount, limit_price, stop_price, style)
        o = self._backend.order(asset, amount, style)
        if o:
            return o.id

    @api_method
    def add_event(self, rule=None, callback=None):
        raise NotImplementedError

    @api_method
    def schedule_function(self,
                          func,
                          date_rule=None,
                          time_rule=None,
                          half_days=True,
                          calendar=None):
        raise NotImplementedError

    @api_method
    def record(self, *args, **kwargs):
        '''Just do nothing for compatibility.'''
        pass

    @api_method
    def set_benchmark(self, benchmark):
        '''Just do nothing for compatibility.'''
        pass

    @api_method
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
            equities (List[Equity]): The equity object lookuped by the ``symbol``.

        Raises:
            AssetNotFound: When could not resolve the ``Asset`` by ``symbol``.
        '''
        raise [self.symbol(idendifier, **kwargs) for idendifier in args]

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
        return [self.order(*order_args) for order_args in order_arg_lists]

    @api_method
    def order_value(self, asset, value, limit_price=None, stop_price=None, style=None):
        return NotImplementedError

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

    def set_logger(self, logger):
        self.logger = logger

    def on_dt_changed(self, dt):
        self._portfolio_needs_update = True
        self._account_needs_update = True
        self.datetime = dt
        self._bardata.datetime = dt

    @api_method
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
        raise APINotSupported

    @property
    def data_frequency(self):
        return self._data_frequency

    @api_method
    def order_percent(self, asset, percent, limit_price=None, stop_price=None, style=None):
        raise NotImplementedError

    @api_method
    def order_target(self, asset, target, limit_price=None, stop_price=None, style=None):
        raise NotImplementedError

    @api_method
    def order_target_value(self, asset, target, limit_price=None, stop_price=None, style=None):
        raise NotImplementedError

    @api_method
    def order_target_percent(self, asset, target, limit_price=None, stop_price=None, style=None):
        raise NotImplementedError

    @api_method
    def batch_market_order(self, share_counts):
        raise NotImplementedError

    @api_method
    def get_open_orders(self, asset=None):
        orders = self._backend.orders

        assets = set([
            order.asset
            for order in orders.items()
            if order.open
        ])

        return {
            asset: [order for order in orders.items()
                    if order.asset == asset and order.open]
            for asset in assets
        }

    @api_method
    def get_order(self, order_id):
        orders = self._backend.orders
        if order_id in orders:
            return orders[order_id].to_api_obj()

    @api_method
    def cancel_order(self, order_param):
        order_id = order_param
        if isinstance(order_param, proto.Order):
            order_id = order_param.id
        self._backend.cancel(order_id)

    @api_method
    def history(self, bar_count, frequency, field, ffill=True):
        """DEPRECATED: use ``data.history`` instead.
        """

        return self.get_history_window(
            bar_count,
            frequency,
            self._calculated_universe(),
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
        # self.validate_order_params(asset,
        #                            amount,
        #                            limit_price,
        #                            stop_price,
        #                            style)

        # Convert deprecated limit_price and stop_price parameters to use
        # ExecutionStyle objects.
        style = self.__convert_order_params_for_blotter(limit_price,
                                                        stop_price,
                                                        style)
        return amount, style

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

    def _calculated_universe(self):
        # this exists to provide backwards compatibility for older,
        # deprecated APIs, particularly around the iterability of
        # BarData (ie, 'for sid in data`).

        # our universe is all the assets passed into `run`.
        return self._assets_from_source

    #
    # Account Controls
    #

    @api_method
    def set_max_leverage(self, max_leverage):
        raise APINotSupported

    @api_method
    def set_max_position_size(self, asset=None, max_shares=None, max_notional=None, on_error='fail'):
        raise APINotSupported

    @api_method
    def set_max_order_size(self,
                           asset=None,
                           max_shares=None,
                           max_notional=None,
                           on_error='fail'):
        raise APINotSupported

    @api_method
    def set_max_order_count(self, max_count, on_error='fail'):
        raise APINotSupported

    @api_method
    def set_do_not_order_list(self, restricted_list, on_error='fail'):
        raise NotImplementedError

    @api_method
    def set_asset_restrictions(self, restrictions, on_error='fail'):
        raise APINotSupported

    @api_method
    def set_long_only(self, on_error='fail'):
        raise APINotSupported

    @api_method
    def attach_pipeline(self, pipeline, name, chunks=None):
        raise APINotSupported

    @api_method
    def pipeline_output(self, name):
        raise APINotSupported
