#
# Copyright 2018 Alpaca
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
import os

import alpaca_trade_api as tradeapi
from alpaca_trade_api.rest import APIError
from alpaca_trade_api.entity import Order
from requests.exceptions import HTTPError
import numpy as np
import pandas as pd
from trading_calendars import (
    get_calendar,
    register_calendar_alias,
)
from trading_calendars.calendar_utils import (
    global_calendar_dispatcher as default_calendar,
)
from datetime import timedelta
import uuid

from .base import BaseBackend

from pylivetrader.api import symbol as symbol_lookup

from pylivetrader.misc.api_context import set_context
import pylivetrader.protocol as zp
from pylivetrader.finance.order import (
    Order as ZPOrder,
    ORDER_STATUS as ZP_ORDER_STATUS,
)
from pylivetrader.finance.execution import (
    MarketOrder,
    LimitOrder,
    StopOrder,
    StopLimitOrder,
)
from pylivetrader.misc.pd_utils import normalize_date
from pylivetrader.misc.parallel_utils import parallelize, \
    parallelize_with_multi_process
from pylivetrader.errors import SymbolNotFound
from pylivetrader.assets import Equity

from logbook import Logger

from threading import Thread
import asyncio

log = Logger('Alpaca')

NY = 'America/New_York'
# alpaca support get real-time data of multi stocks(<200) at once. we use this:
ALPACA_MAX_SYMBOLS_PER_REQUEST = 199

end_offset = pd.Timedelta('1000 days')
one_day_offset = pd.Timedelta('1 day')


def skip_http_error(statuses):
    """
    A decorator to wrap with try..except to swallow
    specific HTTP errors.

    @skip_http_error((404, 503))
    def fetch():
        ...
    """

    assert isinstance(statuses, tuple)

    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except HTTPError as e:
                status_code = e.response.status_code
                if status_code in statuses:
                    log.warn(str(e))
                else:
                    raise
        return wrapper
    return decorator


class Backend(BaseBackend):

    def __init__(
        self,
        key_id=None,
        secret=None,
        base_url=None,
        api_version='v2',
        use_polygon=False
    ):
        self._key_id = key_id
        self._secret = secret
        self._base_url = base_url
        self._use_polygon = use_polygon
        self._api = tradeapi.REST(
            key_id, secret, base_url, api_version=api_version
        )
        self._cal = get_calendar('NYSE')

        self._open_orders = {}
        self._orders_pending_submission = {}

    def initialize_data(self, context):
        # Open a websocket stream to get updates in real time
        stream_process = Thread(
            target=self._get_stream, daemon=True, args=(context,)
        )
        stream_process.start()

        # Load all open orders
        existing_orders = self.all_orders(status='open', initialize=True)
        for k, v in existing_orders.items():
            if self._open_orders.get(k) is not None:
                self._open_orders[k] += v
            else:
                self._open_orders[k] = v

    def _get_stream(self, context):
        set_context(context)
        asyncio.set_event_loop(asyncio.new_event_loop())
        conn = tradeapi.StreamConn(
            self._key_id,
            self._secret,
            self._base_url,
            data_url=os.environ.get("DATA_PROXY_WS", ''),
            data_stream='polygon' if self._use_polygon else 'alpacadatav1'
        )
        channels = ['trade_updates']

        @conn.on(r'trade_updates')
        async def handle_trade_update(conn, channel, data):
            # Check for any pending orders
            waiting_order = self._orders_pending_submission.get(
                data.order['client_order_id']
            )
            if waiting_order is not None:
                if data.event == 'fill':
                    # Submit the waiting order
                    self.order(*waiting_order)
                    self._orders_pending_submission.pop(
                        data.order['client_order_id'], None
                    )
                elif data.event in ['canceled', 'rejected']:
                    # Remove the waiting order
                    self._orders_pending_submission.pop(
                        data.order['client_order_id'], None
                    )

            if data.event in ['canceled', 'rejected', 'fill']:
                self._open_orders.pop(data.order['client_order_id'], None)
            else:
                self._open_orders[data.order['client_order_id']] = (
                    self._order2zp(Order(data.order))
                )
        while 1:
            try:
                conn.run(channels)
                log.info("Connection reestablished")
            except Exception:
                from time import sleep
                sleep(5)
                asyncio.set_event_loop(asyncio.new_event_loop())

    def _symbols2assets(self, symbols):
        '''
        Utility for debug/testing
        '''

        assets = {a.symbol: a for a in self.get_equities()}
        return [assets[symbol] for symbol in symbols if symbol in assets]

    def get_equities(self):
        assets = []
        t = normalize_date(pd.Timestamp('now', tz=NY))
        raw_assets = self._api.list_assets(asset_class='us_equity')
        for raw_asset in raw_assets:

            asset = Equity(
                raw_asset.id, raw_asset.exchange,
                symbol=raw_asset.symbol,
                asset_name=raw_asset.symbol,
            )

            asset.start_date = t - one_day_offset

            if raw_asset.status == 'active' and raw_asset.tradable:
                asset.end_date = t + end_offset
            else:
                # if asset is not tradable, set end_date = day before
                asset.end_date = t - one_day_offset
            asset.auto_close_date = asset.end_date

            assets.append(asset)

            # register all unseen exchange name as
            # alias of NYSE (e.g. AMEX, ARCA, NYSEARCA.)
            if not default_calendar.has_calendar(raw_asset.exchange):
                register_calendar_alias(raw_asset.exchange,
                                        'NYSE', force=True)

        return assets

    @property
    def positions(self):
        z_positions = zp.Positions()
        positions = self._api.list_positions()
        position_map = {}
        symbols = []
        for pos in positions:
            symbol = pos.symbol
            try:
                z_position = zp.Position(symbol_lookup(symbol))
            except SymbolNotFound:
                continue
            z_position.amount = int(pos.qty)
            z_position.cost_basis = float(pos.cost_basis) / float(pos.qty)
            z_position.last_sale_price = None
            z_position.last_sale_date = None
            z_positions[symbol_lookup(symbol)] = z_position
            symbols.append(symbol)
            position_map[symbol] = z_position

        trades = self._get_symbols_last_trade_value(symbols)
        for symbol, trade in trades.items():
            z_position = position_map[symbol]
            if trade is None:
                z_position.last_sale_price = np.nan
                z_position.last_sale_date = pd.NaT
            else:
                z_position.last_sale_price = float(trade.price)
                z_position.last_sale_date = trade.timestamp
        return z_positions

    @property
    def portfolio(self):
        account = self._api.get_account()
        z_portfolio = zp.Portfolio()
        z_portfolio.cash = float(account.cash)
        z_portfolio.positions = self.positions
        z_portfolio.positions_value = float(
            account.portfolio_value) - float(account.cash)
        z_portfolio.portfolio_value = float(account.portfolio_value)
        return z_portfolio

    @property
    def account(self):
        account = self._api.get_account()
        z_account = zp.Account()
        z_account.buying_power = float(account.buying_power)
        z_account.total_position_value = float(
            account.portfolio_value) - float(account.cash)
        return z_account

    def _order2zp(self, order):
        zp_order = ZPOrder(
            id=order.client_order_id,
            asset=symbol_lookup(order.symbol),
            amount=int(order.qty) if order.side == 'buy' else -int(order.qty),
            stop=float(order.stop_price) if order.stop_price else None,
            limit=float(order.limit_price) if order.limit_price else None,
            dt=order.submitted_at,
            commission=0,
        )
        zp_order._status = ZP_ORDER_STATUS.OPEN
        if order.canceled_at:
            zp_order._status = ZP_ORDER_STATUS.CANCELLED
        if order.failed_at:
            zp_order._status = ZP_ORDER_STATUS.REJECTED
        if order.filled_at:
            zp_order._status = ZP_ORDER_STATUS.FILLED
            zp_order.filled = int(order.filled_qty)
        return zp_order

    def _new_order_id(self):
        return uuid.uuid4().hex

    def batch_order(self, args):
        return [self.order(*order) for order in args]

    def order(self, asset, amount, style, quantopian_compatible=True):
        symbol = asset.symbol
        zp_order_id = self._new_order_id()

        if quantopian_compatible:
            current_position = self.positions[asset]
            if (
                abs(amount) > abs(current_position.amount) and
                amount * current_position.amount < 0
            ):
                # The order would take us from a long position to a short
                # position or vice versa and needs to be broken up
                self._orders_pending_submission[zp_order_id] = (
                    asset,
                    amount + current_position.amount,
                    style
                )
                amount = -1 * current_position.amount

        qty = amount if amount > 0 else -amount

        side = 'buy' if amount > 0 else 'sell'
        order_type = 'market'
        if isinstance(style, MarketOrder):
            order_type = 'market'
        elif isinstance(style, LimitOrder):
            order_type = 'limit'
        elif isinstance(style, StopOrder):
            order_type = 'stop'
        elif isinstance(style, StopLimitOrder):
            order_type = 'stop_limit'

        limit_price = style.get_limit_price(side == 'buy') or None
        stop_price = style.get_stop_price(side == 'buy') or None

        log.debug(
            ('submitting {} order for {} - '
             'qty:{}, side:{}, limit_price:{}, stop_price:{}').format(
                order_type,
                symbol,
                qty,
                side,
                limit_price,
                stop_price
            )
        )
        try:
            order = self._api.submit_order(
                symbol=symbol,
                qty=qty,
                side=side,
                type=order_type,
                time_in_force='day',
                limit_price=limit_price,
                stop_price=stop_price,
                client_order_id=zp_order_id,
            )
            zp_order = self._order2zp(order)
            self._open_orders[zp_order_id] = zp_order
            return zp_order
        except APIError as e:
            log.warning('order for symbol {} is rejected {}'.format(
                symbol,
                e
            ))
            return None

    @property
    def orders(self):
        return {
            o.client_order_id: self._order2zp(o)
            for o in self._api.list_orders('all')
        }

    def get_order(self, zp_order_id):
        order = None
        try:
            order = self._open_orders[zp_order_id]
        except Exception:
            # Order was not found in our open order list, may be closed
            order = self._order2zp(
                self._api.get_order_by_client_order_id(zp_order_id))
        return order

    def all_orders(
            self,
            before=None,
            status='all',
            days_back=None,
            initialize=False):
        # Check if the open order list is being asked for
        if (not initialize and status == 'open'
           and before is None and days_back is None):
            return self._open_orders

        # Get all orders submitted days_back days before `before` or now.
        now = pd.Timestamp.utcnow()
        start = now.isoformat() if before is None else before.isoformat()

        # A session label refers to the market date that an order submitted
        # at a given minute would be executed on. We'll need to keep track of
        # this if the function is bounded by days_back.
        start_session_label = self._cal.minute_to_session_label(now)
        reached_end_date = False

        all_orders = {}
        batch_size = 500

        orders = self._api.list_orders(status, batch_size, until=start)
        while len(orders) > 0 and not reached_end_date:
            batch_orders = {}
            for order in orders:
                if days_back is not None:
                    # Verify that the order is not too old.
                    # `session_distance()` ignores holidays and weekends.
                    days_since_order = self._cal.session_distance(
                        self._cal.minute_to_session_label(order.submitted_at),
                        start_session_label
                    )
                    if days_since_order > days_back:
                        reached_end_date = True
                        break
                batch_orders[order.client_order_id] = self._order2zp(order)
            all_orders.update(batch_orders)
            if not reached_end_date:
                # Get the timestamp of the earliest order in the batch.
                until = pd.Timestamp(orders[-1].submitted_at).isoformat()
                orders = self._api.list_orders(status, batch_size, until=until)
        return all_orders

    def cancel_order(self, zp_order_id):
        try:
            order = self._api.get_order_by_client_order_id(zp_order_id)
            self._api.cancel_order(order.id)
        except Exception as e:
            print('Error: Could not cancel order {}'.format(zp_order_id))
            log.error(e)
            return

    def get_last_traded_dt(self, asset):
        if self._use_polygon:
            trade = self._api.polygon.last_trade(asset.symbol)
        else:
            trade = self._api.get_last_trade(asset.symbol)
        return trade.timestamp

    def get_spot_value(
            self,
            assets,
            field,
            dt,
            date_frequency,
            quantopian_compatible=True):
        assert(field in (
            'open', 'high', 'low', 'close', 'volume', 'price', 'last_traded'))
        assets_is_scalar = not isinstance(assets, (list, set, tuple))
        if assets_is_scalar:
            symbols = [assets.symbol]
        else:
            symbols = [asset.symbol for asset in assets]
        if field == 'last_traded' or \
           not quantopian_compatible and field == 'price':
            results = self._get_spot_trade(symbols, field)
        else:
            results = self._get_spot_bars(symbols, field)
        return results[0] if assets_is_scalar else results

    def _get_spot_trade(self, symbols, field):
        assert(field in ('price', 'last_traded'))
        symbol_trades = self._get_symbols_last_trade_value(symbols)

        def get_for_symbol(symbol_trades, symbol):
            trade = symbol_trades.get(symbol)
            if field == 'price':
                if trade is None:
                    return np.nan
                return trade.price
            else:
                if trade is None:
                    return pd.NaT
                return trade.timestamp

        return [get_for_symbol(symbol_trades, symbol) for symbol in symbols]

    def _get_symbols_last_trade_value(self, symbols):
        """
        Query last_trade in parallel for multiple symbols and
        return in dict.

        symbols: list[str]

        return: dict[str -> polygon.Trade or alpaca.Trade]
        """

        @skip_http_error((404, 504))
        def fetch(symbol):
            if self._use_polygon:
                return self._api.polygon.last_trade(symbol)
            else:
                return self._api.get_last_trade(symbol)

        return parallelize(fetch)(symbols)

    def _get_spot_bars(self, symbols, field):
        symbol_bars = self._fetch_bars_from_api(symbols,
                                                'minute',
                                                limit=1)

        def get_for_symbol(symbol_bars, symbol, field):
            bars = symbol_bars.get(symbol)
            if bars is None or len(bars) == 0:
                return np.nan
            return bars[field].values[-1]

        ohlcv_field = 'close' if field == 'price' else field
        results = [
            get_for_symbol(symbol_bars, symbol, ohlcv_field)
            for symbol in symbols
        ]
        return results

    def get_bars(self, assets, data_frequency, bar_count=500, end_dt=None):
        """
        Interface method.

        Return: pd.Dataframe() with columns MultiIndex [asset -> OHLCV]
        """
        assets_is_scalar = not isinstance(assets, (list, set, tuple))
        is_daily = 'd' in data_frequency  # 'daily' or '1d'
        if assets_is_scalar:
            symbols = [assets.symbol]
        else:
            symbols = [asset.symbol for asset in assets]

        df = self._fetch_bars_from_api(
            symbols,
            'day' if is_daily else 'minute',
            to=end_dt,
            limit=bar_count)

        # change the index values to assets to compatible with zipline
        symbol_asset = {a.symbol: a for a in assets} if not assets_is_scalar \
            else {assets.symbol: assets}
        df.columns = df.columns.set_levels([
            symbol_asset[s] for s in df.columns.levels[0]], level=0)
        return df

    def _fetch_bars_from_api(
            self,
            symbols,
            size,
            _from=None,
            to=None,
            limit=None):
        """
        Query history bars either minute or day in parallel
        for multiple symbols

        you can pass:
        1 _from + to
        2 to + limit
        3 limit, this way will use the current time as to

        symbols: list[str]
        size:    str ('day', 'minute')
        _from:   str or pd.Timestamp
        to:      str or pd.Timestamp
        limit:   str or int

        return: MultiIndex dataframe that looks like this:
                       AA                          GOOG
                       open high low close volume  open high low close volume
        DatetimeIndex:

        columns: level 0 equity name, level 1 OHLCV

        """
        assert size in ('day', 'minute')

        assert (_from and to) or limit

        if not (_from and to):
            _from, to = self._get_from_and_to(size, limit, end_dt=to)
        if self._use_polygon:
            args = [{'symbols': symbol,
                     '_from': _from,
                     "to": to,
                     "size": size}
                    for symbol in symbols]
            result = parallelize(self._fetch_bars_from_api_internal)(args)
            if [df for df in result.values() if isinstance(df, pd.DataFrame)]:
                return pd.concat(result.values(), axis=1)
            else:
                return pd.DataFrame([])

        else:
            # alpaca support get real-time data of multi stocks(<200) at once
            parts = []
            for i in range(0, len(symbols), ALPACA_MAX_SYMBOLS_PER_REQUEST):
                part = symbols[i:i + ALPACA_MAX_SYMBOLS_PER_REQUEST]
                parts.append(part)
            args = [{'symbols': part,
                     '_from': _from,
                     "to": to,
                     "size": size,
                     "limit": limit} for part in parts]
            result = parallelize_with_multi_process(
                self._fetch_bars_from_api_internal)(args)

            return pd.concat(result, axis=1)

    def _get_from_and_to(self, size, limit, end_dt=None):
        """
        this method returns the trading time range. if end_dt is not
        a session time，it will be adjusted to the nearest last trading
        minute. when size=daily, will return a timestamp of midnight.

        return: tuple(pd.Timestamp(tz=America/New_York))
        """
        if not end_dt:
            end_dt = pd.to_datetime('now', utc=True).floor('min')
        session_label = self._cal.minute_to_session_label(end_dt)
        all_minutes: pd.DatetimeIndex = self._cal.all_minutes
        all_sessions: pd.DatetimeIndex = self._cal.all_sessions
        if size == 'minute':
            if end_dt not in self._cal.minutes_for_session(session_label):
                end_dt = self._cal.previous_minute(end_dt)
                # Alpaca's last minute is 15:59 not 16:00 (NY tz)
                end_dt = end_dt - timedelta(minutes=1)
            idx = all_minutes.get_loc(end_dt)
            start_minute = all_minutes[idx - limit + 1] if limit != 1 else \
                all_minutes[idx - limit]
            _from = start_minute.tz_convert(NY)
            to = end_dt.tz_convert(NY)
        elif size == 'day':
            idx = all_sessions.get_loc(session_label)
            start_session = all_sessions[idx - limit + 1]
            _from = start_session.tz_localize(
                None).tz_localize('America/New_York')
            to = session_label.tz_localize(
                None).tz_localize('America/New_York')

        return _from, to

    def _fetch_bars_from_api_internal(self, params):
        """
        this method is used by parallelize_with_multi_process or parallelize.
        params: dict with keys in ['symbols', '_from', 'to', 'size']
        """
        @skip_http_error((404, 504))
        def wrapper():
            symbols = params['symbols']  # symbols can be list or str
            _from = params['_from']
            to = params['to']
            size = params['size']
            if self._use_polygon:
                assert isinstance(symbols, str)
                symbol = str(symbols)
                df = self._api.polygon.historic_agg_v2(
                    symbol, 1, size,
                    int(_from.timestamp()) * 1000,
                    int(to.timestamp()) * 1000
                ).df
                df.columns = pd.MultiIndex.from_product([[symbols, ],
                                                         df.columns])
            else:
                df = self._api.get_barset(symbols,
                                          size,
                                          limit=params['limit'],
                                          start=_from.isoformat(),
                                          end=to.isoformat()).df[symbols]

            # zipline -> right label
            # API result -> left label (beginning of bucket)
            if size == 'minute':
                df.index += pd.Timedelta('1min')

                if not df.empty:
                    # mask out bars outside market hours
                    mask = self._cal.minutes_in_range(
                        df.index[0], df.index[-1],
                    ).tz_convert(NY)
                    df = df.reindex(mask)
            return df
        return wrapper()
