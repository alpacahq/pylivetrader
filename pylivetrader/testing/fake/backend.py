from pylivetrader import api
from pylivetrader.assets import Asset

import pylivetrader.protocol as zp
from pylivetrader.assets import Equity
from pylivetrader.finance.order import (
    Order as ZPOrder,
    ORDER_STATUS as ZP_ORDER_STATUS,
)
from pylivetrader.backend.base import BaseBackend
import pandas as pd

from logbook import Logger

log = Logger(__name__)


class Backend(BaseBackend):
    def __init__(self, proxy, cash=1e6):
        self._proxy = proxy
        self._account = zp.Account()
        self._account.buying_power = cash
        self._account.total_position_value = 0
        self._portfolio = zp.Portfolio()
        self._portfolio.cash = cash
        self._portfolio.positions = self._positions = zp.Positions()
        self._order_seq = 0
        self._orders = {}
        self._clock = None
        self._real_bars = {'1d': {}, '1m': {}}

    def set_clock(self, clock):
        self._clock = clock

    @property
    def now(self):
        if self._clock is not None:
            return self._clock.now
        return pd.Timestamp.now(tz='America/New_York')

    def _fill(self, order, price):
        pos = self._positions.pop(order.asset, None)
        if pos is None:
            pos = zp.Position(order.asset)
            pos.amount = 0
            pos.cost_basis = 0

        new_amount = pos.amount + order.amount
        if new_amount < 0:
            log.warn('not enough shares')
            return
        volume = price * order.amount
        self._portfolio.cash -= volume
        self._account.cash = self._portfolio.cash
        self._account.buying_power -= volume

        if new_amount == 0:
            return

        new_volume = price * order.amount + pos.cost_basis * pos.amount
        pos.cost_basis = new_volume / new_amount
        pos.amount = new_amount
        pos.last_sale_date = self.now
        self._positions[order.asset] = pos

    def _process_orders(self):
        for order in self._orders.values():
            asset = order.asset
            price_df = self.get_bars([asset], '1m')[asset]
            price_df[order.dt:]
            if order.amount > 0:
                max_price = price_df.high.max()
                price = price_df.close.values[-1]
                if order.limit is not None and order.stop is not None:
                    # STOP LIMIT
                    if price <= order.limit and max_price >= order.stop:
                        self._fill(order, price)
                elif order.limit is not None:
                    # LIMIT
                    if price <= order.limit:
                        self._fill(order, price)
                elif order.stop is not None:
                    # STOP
                    if max_price >= order.stop:
                        self._fill(order, price)
                else:
                    # MARKET
                    self._fill(order, price)
            else:
                min_price = price_df.low.min()
                price = price_df.close.values[-1]
                if order.limit is not None and order.stop is not None:
                    # STOP LIMIT
                    if price >= order.limit and min_price <= order.stop:
                        self._fill(order, price)
                elif order.limit is not None:
                    # LIMIT
                    if price >= order.limit:
                        self._fill(order, price)
                elif order.stop is not None:
                    # STOP
                    if min_price <= order.stop:
                        self._fill(order, price)
                else:
                    # MARKET
                    self._fill(order, price)
        self._portfolio.positions_value = sum([
            p.cost_basis * p.amount for p in self._positions.values()
        ])
        self._portfolio.portfolio_value = self._portfolio.cash + \
            self._portfolio.positions_value

    def get_equities(self):
        return self._proxy.get_equities()

    @property
    def positions(self):
        self._process_orders()
        return self._positions

    def set_position(self, symbol, amount, cost_basis,
                     last_sale_price=None, last_sale_date=None):
        asset = api.symbol(symbol) if isinstance(symbol, str) else symbol
        pos = zp.Position(asset)
        pos.amount = amount
        pos.cost_basis = cost_basis
        pos.last_sale_price = last_sale_price
        pos.last_sale_date = last_sale_date
        self._positions[asset] = pos

    @property
    def portfolio(self):
        self._process_orders()
        return self._portfolio

    @property
    def account(self):
        return self._account

    @property
    def orders(self):
        return self._orders

    def batch_order(self, args):
        return [self.order(*order) for order in args]

    def order(self, asset, amount, style):
        limit_price = style.get_limit_price(amount > 0) or None
        stop_price = style.get_stop_price(amount > 0) or None
        self._order_seq += 1
        zpOrder = ZPOrder(
            dt=self.get_last_traded_dt(asset),
            asset=asset,
            amount=amount,
            limit=limit_price,
            stop=stop_price,
            id=self._order_seq,
        )
        self._orders[zpOrder.id] = zpOrder
        return zpOrder

    def cancel_order(self, zp_order_id):
        if zp_order_id in self._orders:
            del self._orders[zp_order_id]

    def get_last_traded_dt(self, asset):
        return self.now

    def get_spot_value(self, assets, field, dt, data_frequency):
        now = self.now

        def _get_for_symbol(df, field):
            _field = field
            if field == 'last_traded':
                return df.index[-1]
            elif field == 'price':
                _field = 'close'
            return df[_field].values[-1]

        if isinstance(assets, Asset):
            df = self._get_real_bars([assets], '1m')[assets][:now]
            return _get_for_symbol(df, field)

        dfs = self._get_real_bars(assets, '1m')
        return [
            _get_for_symbol(dfs[asset][:now], field) for asset in assets
        ]

    def get_bars(self, assets, data_frequency, bar_count=500):
        now = self.now
        real_bars = self._get_real_bars(assets, data_frequency)
        items = []
        for asset in assets:
            df = real_bars[asset][:now].iloc[-bar_count:]
            df.columns = pd.MultiIndex.from_product([[asset, ], df.columns])
            items.append(df)
        return pd.concat(items, axis=1)

    def _get_real_bars(self, assets, data_frequency):
        missing = []
        for asset in assets:
            if asset not in self._real_bars[data_frequency]:
                missing.append(asset)

        if missing:
            data = self._proxy.get_bars(
                missing, data_frequency, bar_count=3000)
            for asset in missing:
                df = data[asset]
                self._real_bars[data_frequency][asset] = df
        return {asset: self._real_bars[data_frequency][asset]
                for asset in assets}
