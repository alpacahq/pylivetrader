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

import pandas as pd

import numpy as np
import uuid
import alpaca_trade_api as tradeapi
from alpaca_trade_api.rest import APIError

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


class Backend(BaseBackend):

    def __init__(self, key_id=None, secret=None, base_url=None):
        self._api = tradeapi.REST(key_id, secret, base_url)

    def get_equities(self):
        assets = []
        t = normalize_date(pd.Timestamp('now', tz='America/New_York'))
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

        quotes = self._api.list_quotes(symbols)
        for quote in quotes:
            price = quote.last
            dt = quote.last_timestamp
            z_position = position_map[quote.symbol]
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
        z_account.buying_power = float(account.cash)
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
        dt = pd.to_datetime('now', utc=True)
        zp_order = ZPOrder(
            dt=dt,
            asset=asset,
            amount=amount,
            stop=stop_price,
            limit=limit_price,
            id=zp_order_id,
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
                client_order_id=zp_order.id,
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
        quote = self._api.get_quote(asset.symbol)
        return pd.Timestamp(quote.last_timestamp)

    def get_spot_value(self, assets, field, dt, data_frequency):
        assert(field in (
            'open', 'high', 'low', 'close', 'volume', 'price', 'last_traded'))
        assets_is_scalar = not isinstance(assets, (list, set, tuple))
        if assets_is_scalar:
            symbols = [assets.symbol]
        else:
            symbols = [asset.symbol for asset in assets]
        if field in ('price', 'last_traded'):
            quotes = self._api.list_quotes(symbols)
            if assets_is_scalar:
                if field == 'price':
                    if len(quotes) == 0:
                        return np.nan
                    return quotes[-1].last
                else:
                    if len(quotes) == 0:
                        return pd.NaT
                    return quotes[-1].last_timestamp
            else:
                return [
                    quote.last if field == 'price' else quote.last_timestamp
                    for quote in quotes
                ]

        bars_list = self._api.list_bars(symbols, '1Min', limit=1)
        if assets_is_scalar:
            if len(bars_list) == 0:
                return np.nan
            return bars_list[0].bars[-1]._raw[field]
        bars_map = {a.symbol: a for a in bars_list}
        return [
            bars_map[symbol].bars[-1]._raw[field]
            for symbol in symbols
        ]

    def get_bars(self, assets, data_frequency, bar_count=500):
        assets_is_scalar = not isinstance(assets, (list, set, tuple))
        is_daily = 'd' in data_frequency  # 'daily' or '1d'
        if assets_is_scalar:
            symbols = [assets.symbol]
        else:
            symbols = [asset.symbol for asset in assets]
        timeframe = '1D' if is_daily else '1Min'

        bars_list = self._api.list_bars(symbols, timeframe, limit=bar_count)
        bars_map = {a.symbol: a for a in bars_list}

        if is_daily:
            intra_bars = {}
            intra_list = self._api.list_bars(symbols, '1Min', limit=1000)
            for bars in intra_list:
                symbol = bars.symbol
                df = _fix_tz(bars.df)
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
            df = bars_map[symbol].df.copy()
            df = _fix_tz(df)
            if is_daily:
                agged = intra_bars[symbol]
                if agged.index[-1] not in df.index:
                    assert agged.index[-1] > df.index[-1]
                    df = df.append(agged.iloc[-1])
            df.columns = pd.MultiIndex.from_product([[asset, ], df.columns])
            dfs.append(df)

        if len(dfs) > 0:
            return pd.concat(dfs, axis=1)

        return pd.DataFrame()


def _fix_tz(df):
    if df.index.tz is None:
        df.index = df.index.tz_localize('UTC').tz_convert(NY)
    return df
