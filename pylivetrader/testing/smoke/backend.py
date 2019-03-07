from pylivetrader import api
from pylivetrader.assets import Asset

import pylivetrader.protocol as zp
from pylivetrader.assets import Equity
from pylivetrader.finance.order import (
    Order as ZPOrder,
)
from pylivetrader.backend.base import BaseBackend
import pandas as pd
import numpy as np
import string
from trading_calendars import get_calendar

from logbook import Logger

log = Logger(__name__)

MAX_FAKE_BARS = 3000


def _num_to_symbol(n):
    buf = []
    while n >= 0:
        a = n % 26
        b = n // 26 - 1
        c = string.ascii_uppercase[a]
        buf.append(c)
        n = b
    return ''.join(reversed(buf))


def _check_fill(order, price_df):
    price = price_df.close.values[-1]
    if order.amount > 0:
        max_price = price_df.high.max()
        if order.limit is not None and order.stop is not None:
            # STOP LIMIT
            return price <= order.limit and max_price >= order.stop
        elif order.stop is not None:
            # STOP
            return max_price >= order.stop
        elif order.limit is not None:
            # LIMIT
            return price <= order.limit
        else:
            # MARKET
            return True
    else:
        min_price = price_df.low.min()
        if order.limit is not None and order.stop is not None:
            # STOP LIMIT
            return price >= order.limit and min_price <= order.stop
        elif order.stop is not None:
            # STOP
            return min_price <= order.stop
        elif order.limit is not None:
            # LIMIT
            return price >= order.limit
        else:
            # MARKET
            return True
    return False


class Backend(BaseBackend):
    '''This backend is a minimal simulator with
    naive order filling for mainly smoke testing.
    The price data is supplied by fake data generator.
    '''

    def __init__(self, cash=1e6, size=50, clock=None):
        '''
        paramters:
            cash: initial cash balance
            size: the number of stocks in universe
            clock: soft clock
        '''
        self._account = zp.Account()
        self._account.buying_power = cash
        self._account.total_position_value = 0
        self._portfolio = zp.Portfolio()
        self._portfolio.cash = cash
        self._portfolio.positions = self._positions = zp.Positions()
        self._order_seq = 0
        self._orders = {}
        self._clock = clock
        self._last_process_time = None

        self._data_proxy = FakeDataBackend(size=size, clock=clock)

    @property
    def now(self):
        if self._clock is not None:
            return self._clock.now
        return pd.Timestamp.now(tz='America/New_York')

    def _fill(self, order, price):
        '''Fill the order at this price and delete the order
        from the pending list.'''
        del self._orders[order.id]
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
        if self._last_process_time == self.now:
            return
        # materialize the list so that _fill() can delete entry.
        for order in list(self._orders.values()):
            asset = order.asset
            price_df = self.get_bars([asset], '1m')[asset]
            price_df = price_df[order.dt:]

            if _check_fill(order, price_df):
                self._fill(order, price_df.close.values[-1])

        posval = self._portfolio.positions_value = sum([
            p.cost_basis * p.amount for p in self._positions.values()
        ])
        self._portfolio.portfolio_value = self._portfolio.cash + posval
        self._last_process_time = self.now

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
    def positions(self):
        self._process_orders()
        return self._positions

    @property
    def portfolio(self):
        self._process_orders()
        return self._portfolio

    @property
    def account(self):
        return self._account

    @property
    def orders(self):
        self._process_orders()
        return self._orders

    def batch_order(self, args):
        return [self.order(*order) for order in args]

    def order(self, asset, amount, style, quantopian_compatible=True):
        if amount == 0:
            return
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

    def get_equities(self):
        return self._data_proxy.get_equities()

    def get_last_traded_dt(self, asset):
        return self._data_proxy.get_last_traded_dt(asset)

    def get_spot_value(
            self,
            assets,
            field,
            dt,
            data_frequency,
            quantopian_compatible=True):
        return self._data_proxy.get_spot_value(
            assets, field, dt, data_frequency)

    def get_bars(self, assets, data_frequency, bar_count=500):
        return self._data_proxy.get_bars(assets, data_frequency, bar_count)

    def initialize_data(self, context):
        pass


class FakeDataBackend:
    '''A data backend that generates synthesic sin wave price data
    for a synthesically generated fixed universe.
    '''

    def __init__(self, size=50, clock=None):
        self._size = size
        self._clock = clock
        self._cal = get_calendar('NYSE')
        self._fake_bars = {
            '1d': {}, '1m': {},
        }

    def _populate_missing(self, assets, data_frequency):
        '''Populates cache bars that are not filled yet.'''
        missing = []
        for asset in assets:
            if asset not in self._fake_bars[data_frequency]:
                missing.append(asset)

        if len(missing) == 0:
            return

        fake_end = self._clock.end_time
        for asset in missing:
            if data_frequency == '1m':
                mask = self._cal.all_minutes
                end = fake_end
            else:
                mask = self._cal.all_sessions
                end = fake_end.floor('1D')
        mask = mask[mask <= end]
        if len(mask) >= MAX_FAKE_BARS:
            mask = mask[-MAX_FAKE_BARS:]
        mask = mask.tz_convert('America/New_York')

        for asset in missing:
            scale = asset.sid
            x = np.linspace(0, len(mask), len(mask))
            ts = np.abs(np.sin(x)) + 1.0
            df = pd.DataFrame({
                'open': ts * scale,
                'high': ts * scale + 0.5,
                'low': ts * scale - 0.5,
                'close': ts * scale + 0.1,
                'volume': (ts * scale * 1e6).astype(int),
            }, index=mask)

            self._fake_bars[data_frequency][asset] = df

    def get_equities(self):
        return [
            Equity(
                sid=i + 1,
                symbol=_num_to_symbol(i),
                asset_name='Test {}'.format(_num_to_symbol(i)),
                exchange='NYSE',
                start_date=pd.Timestamp('1970-01-01', tz='utc'),
                end_date=pd.Timestamp('2050-01-01', tz='utc'),
            ) for i in range(self._size)
        ]

    def get_last_traded_dt(self, asset):
        return self.now

    def get_spot_value(
            self,
            assets,
            field,
            dt,
            data_frequency,
            quantopian_compatible=True):
        now = self.now

        def _get_for_symbol(df, field):
            _field = field
            if field == 'last_traded':
                return df.index[-1]
            elif field == 'price':
                _field = 'close'
            return df[_field].values[-1]

        if isinstance(assets, Asset):
            df = self.get_bars([assets], '1m')[assets][:now]
            return _get_for_symbol(df, field)

        dfs = self.get_bars(assets, '1m')
        return [
            _get_for_symbol(dfs[asset][:now], field) for asset in assets
        ]

    def get_bars(self, assets, data_frequency, bar_count=500):
        now = self.now

        self._populate_missing(assets, data_frequency)

        items = []
        for asset in assets:
            df = self._fake_bars[data_frequency][asset]
            df = df[df.index <= now]
            df = df.iloc[-bar_count:]
            df.columns = pd.MultiIndex.from_product([[asset, ], df.columns])
            items.append(df)
        return pd.concat(items, axis=1)

    @property
    def now(self):
        if self._clock is not None:
            return self._clock.now
        return pd.Timestamp.now(tz='America/New_York')

    def initialize_data(self, context):
        pass
