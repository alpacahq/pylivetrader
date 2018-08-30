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
import concurrent.futures
from requests.exceptions import HTTPError
import numpy as np
import pandas as pd
from trading_calendars import get_calendar
import uuid

from .base import BaseBackend

from pylivetrader.api import symbol as symbol_lookup
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
from pylivetrader.errors import SymbolNotFound
from pylivetrader.assets import Equity

from logbook import Logger


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


def parallelize(mapfunc, workers=10):
    '''
    Parallelize the mapfunc using multithread partitioned by
    symbol.

    Return: func(symbols: list[str]) => dict[str -> result]
    '''

    def wrapper(symbols):
        result = {}
        with concurrent.futures.ThreadPoolExecutor(
                max_workers=workers) as executor:
            tasks = {}
            for symbol in symbols:
                task = executor.submit(mapfunc, symbol)
                tasks[task] = symbol

            for task in concurrent.futures.as_completed(tasks):
                symbol = tasks[task]
                task_result = task.result()
                result[symbol] = task_result
        return result

    return wrapper


class Backend(BaseBackend):

    def __init__(self, key_id=None, secret=None, base_url=None):
        self._api = tradeapi.REST(key_id, secret, base_url)
        self._cal = get_calendar('NYSE')

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
            price = trade.price
            dt = trade.timestamp
            z_position = position_map[symbol]
            z_position.last_sale_price = float(price)
            z_position.last_sale_date = dt
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

    def order(self, asset, amount, style):
        symbol = asset.symbol
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

        zp_order_id = self._new_order_id()

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
            return zp_order
        except APIError as e:
            log.warning('order is rejected {}'.format(e))
            return None

    @property
    def orders(self):
        return {
            o.client_order_id: self._order2zp(o)
            for o in self._api.list_orders('all')
        }

    def cancel_order(self, zp_order_id):
        try:
            order = self._api.get_order_by_client_order_id(zp_order_id)
            self._api.cancel_order(order.id)
        except Exception as e:
            log.error(e)
            return

    def get_last_traded_dt(self, asset):
        trade = self._api.polygon.last_trade(asset.symbol)
        return trade.timestamp

    def get_spot_value(self, assets, field, dt, data_frequency):
        assert(field in (
            'open', 'high', 'low', 'close', 'volume', 'price', 'last_traded'))
        assets_is_scalar = not isinstance(assets, (list, set, tuple))
        if assets_is_scalar:
            symbols = [assets.symbol]
        else:
            symbols = [asset.symbol for asset in assets]
        if field in ('price', 'last_traded'):
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

        results = [
            get_for_symbol(symbol_bars, symbol, field)
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
            symbols, data_frequency, limit=bar_count)

        if is_daily:
            intra_bars = {}
            symbol_bars_minute = self._symbol_bars(
                symbols, 'minute', limit=1000)
            for symbol, df in symbol_bars_minute.items():
                mask = (df.index.time >= pd.Timestamp('9:30').time()) & (
                    df.index.time < pd.Timestamp('16:00').time())
                agged = df[mask].resample('1D').agg(dict(
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
                    assert agged.index[-1] > df.index[-1]
                    df = df.append(agged.iloc[-1])
            df.columns = pd.MultiIndex.from_product([[asset, ], df.columns])
            dfs.append(df)

        return pd.concat(dfs, axis=1)

    def _symbol_bars(
            self,
            symbols,
            frequency,
            _from=None,
            to=None,
            limit=None):
        '''
        Query historic_agg either minute or daily in parallel
        for multiple symbols, and return in dict.

        symbols:   list[str]
        frequency: str ('daily', 'minute')
        _from:     str or pd.Timestamp
        to:        str or pd.Timestamp
        limit:     str or int

        return: dict[str -> pd.DataFrame]
        '''
        assert frequency in ('daily', 'minute')

        # temp workaround for less bars after masking by
        # market hours
        query_limit = limit
        if query_limit is not None:
            query_limit *= 2
        size = 'day' if frequency == 'daily' else 'minute'

        @skip_http_error((404, 504))
        def fetch(symbol):
            df = self._api.polygon.historic_agg(
                size, symbol, _from, to, query_limit).df

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

        return parallelize(fetch, workers=25)(symbols)

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

        return parallelize(fetch, workers=25)(symbols)
