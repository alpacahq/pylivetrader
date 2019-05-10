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
from pylivetrader.misc.parallel_utils import parallelize
from pylivetrader.errors import SymbolNotFound
from pylivetrader.assets import Equity

from logbook import Logger

from threading import Thread
import asyncio

log = Logger('Alpaca')

NY = 'America/New_York'

end_offset = pd.Timedelta('1000 days')
one_day_offset = pd.Timedelta('1 day')


def skip_http_error(statuses):
    '''
    A decorator to wrap with try..except to swallow
    specific HTTP errors.

    @skip_http_error((404, 503))
    def fetch():
        ...
    '''

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
        api_version='v1'
    ):
        self._key_id = key_id
        self._secret = secret
        self._base_url = base_url
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
        conn = tradeapi.StreamConn(self._key_id, self._secret, self._base_url)
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

        conn.run(channels)

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

        trades = self._symbol_trades(symbols)
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
        trade = self._api.polygon.last_trade(asset.symbol)
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
        if ((quantopian_compatible and field == 'last_traded') or
           (not quantopian_compatible and field in ('price', 'last_traded'))):
            results = self._get_spot_trade(symbols, field)
        else:
            results = self._get_spot_bars(symbols, field)
        return results[0] if assets_is_scalar else results

    def _get_spot_trade(self, symbols, field):
        assert(field in ('price', 'last_traded'))
        symbol_trades = self._symbol_trades(symbols)

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

    def _get_spot_bars(self, symbols, field):
        symbol_bars = self._symbol_bars(symbols, 'minute', limit=1)

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

    def get_bars(self, assets, data_frequency, bar_count=500):
        '''
        Interface method.

        Return: pd.Dataframe() with columns MultiIndex [asset -> OHLCV]
        '''
        assets_is_scalar = not isinstance(assets, (list, set, tuple))
        is_daily = 'd' in data_frequency  # 'daily' or '1d'
        if assets_is_scalar:
            symbols = [assets.symbol]
        else:
            symbols = [asset.symbol for asset in assets]

        symbol_bars = self._symbol_bars(
            symbols, 'day' if is_daily else 'minute', limit=bar_count)

        if is_daily:
            intra_bars = {}
            symbol_bars_minute = self._symbol_bars(
                symbols, 'minute', limit=1000)
            for symbol, df in symbol_bars_minute.items():
                agged = df.resample('1D').agg(dict(
                    open='first',
                    high='max',
                    low='min',
                    close='last',
                    volume='sum',
                )).dropna()
                intra_bars[symbol] = agged

        dfs = []
        for asset in assets if not assets_is_scalar else [assets]:
            symbol = asset.symbol
            df = symbol_bars.get(symbol)
            if df is None:
                dfs.append(pd.DataFrame(
                    [], columns=[
                        'open', 'high', 'low', 'close', 'volume']
                ))
                continue
            if is_daily:
                agged = intra_bars.get(symbol)
                if agged is not None and len(
                        agged.index) > 0 and agged.index[-1] not in df.index:
                    if not (agged.index[-1] > df.index[-1]):
                        log.warn(
                            ('agged.index[-1] = {}, df.index[-1] = {} '
                             'for {}').format(
                                agged.index[-1], df.index[-1], symbol))
                    df = df.append(agged.iloc[-1])
            df.columns = pd.MultiIndex.from_product([[asset, ], df.columns])
            dfs.append(df)

        return pd.concat(dfs, axis=1)

    def _symbol_bars(
            self,
            symbols,
            size,
            _from=None,
            to=None,
            limit=None):
        '''
        Query historic_agg either minute or day in parallel
        for multiple symbols, and return in dict.

        symbols: list[str]
        size:    str ('day', 'minute')
        _from:   str or pd.Timestamp
        to:      str or pd.Timestamp
        limit:   str or int

        return: dict[str -> pd.DataFrame]
        '''
        assert size in ('day', 'minute')

        if not (_from or to):
            to = pd.to_datetime('now', utc=True).tz_convert('America/New_York')

        if not (_from and to) and limit:
            # temp workaround for less bars after masking by
            # market hours
            query_limit = limit
            if query_limit is not None:
                query_limit *= 2

            if _from:
                if size == 'day':
                    to = _from + timedelta(days=query_limit+1)
                else:
                    to = _from + timedelta(minutes=query_limit+1)
            else:
                if size == 'day':
                    _from = to - timedelta(days=query_limit+1)
                else:
                    _from = to - timedelta(minutes=query_limit+1)

        @skip_http_error((404, 504))
        def fetch(symbol):
            df = self._api.polygon.historic_agg_v2(
                symbol, 1, size,
                int(_from.timestamp()) * 1000,
                int(to.timestamp()) * 1000
            ).df

            # rename Polygon's v2 agg fields to match their full titles
            df = df.rename(index=str, columns={
                't': 'timestamp',
                'o': 'open',
                'h': 'high',
                'l': 'low',
                'c': 'close',
                'v': 'volume'
            })

            # convert timestamps to datetimes
            # astype is necessary to deal with empty result
            df.index = pd.to_datetime(
                df.index.astype('int64') * 1000000,
                utc=True,
            ).tz_convert('America/New_York')
            df.index.name = 'timestamp'

            # zipline -> right label
            # API result -> left label (beginning of bucket)
            if size == 'minute':
                df.index += pd.Timedelta('1min')

                # mask out bars outside market hours
                mask = self._cal.minutes_in_range(
                    df.index[0], df.index[-1],
                ).tz_convert(NY)
                df = df.reindex(mask)

            if limit is not None:
                df = df.iloc[-limit:]
            return df

        return parallelize(fetch)(symbols)

    def _symbol_trades(self, symbols):
        '''
        Query last_trade in parallel for multiple symbols and
        return in dict.

        symbols: list[str]

        return: dict[str -> polygon.Trade]
        '''

        @skip_http_error((404, 504))
        def fetch(symbol):
            return self._api.polygon.last_trade(symbol)

        return parallelize(fetch)(symbols)
