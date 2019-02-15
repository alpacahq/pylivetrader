import pandas as pd
import numpy as np

from pylivetrader.data.data_portal import DataPortal
from pylivetrader.assets import AssetFinder
from pylivetrader.assets import Equity
from pylivetrader.misc.pd_utils import normalize_date
from pylivetrader.finance.order import Order as ZPOrder
from trading_calendars import get_calendar


def get_fixture_data_portal(**kwargs):

    b = Backend(**kwargs)

    finder = AssetFinder(b)

    return DataPortal(b, finder, b._calendar, False)


def create_bars(minutes, offset):
    length = len(minutes)
    return pd.DataFrame({
        'open': np.arange(length) + 10 + offset,
        'high': np.arange(length) + 15 + offset,
        'low': np.arange(length) + 8 + offset,
        'close': np.arange(length) + 10 + offset,
        'volume': 100 + offset,
    }, index=minutes)


class Backend:

    def __init__(self, start=None, end=None, assets=None, exchange='NYSE'):
        self.start = normalize_date(pd.Timestamp(start or '2018-08-13'))
        self.end = normalize_date(pd.Timestamp(end or '2018-08-14'))

        self._exchange = exchange
        self._calendar = get_calendar(exchange)

        self.assets = assets or ['asset-0', 'asset-1', 'asset-2']

        minutes = self._calendar.minutes_for_sessions_in_range(
            self.start, self.end)
        self._minutely_bars = {}
        for i, asset in enumerate(self.get_equities()):
            bars = create_bars(minutes, i)
            self._minutely_bars[asset] = bars

        days = self._calendar.sessions_in_range(self.start, self.end)
        self._daily_bars = {}
        for i, asset in enumerate(self.get_equities()):
            bars = create_bars(days, i)
            self._daily_bars[asset] = bars

    def get_equities(self):
        return [
            Equity(
                asset,
                symbol=asset.upper().replace('-', ''),
                exchange='NYSE',
                start_date=self.start,
                end_date=self.end + pd.Timedelta('1000 days'),
            ) for asset in self.assets
        ]

    def get_adjusted_value(self, assets, field, dt, data_frequency):
        return self.get_spot_value(assets, field, dt, data_frequency, False)

    def get_spot_value(
            self,
            assets,
            field,
            dt,
            data_frequency,
            quantopian_compatible=True):
        assets_is_scalar = not isinstance(assets, (list, set, tuple))

        field = 'close' if field == 'price' else field

        if assets_is_scalar:
            if 'd' in data_frequency:
                return self._daily_bars[assets][field].iloc[-1]
            else:
                return self._minutely_bars[assets][field].iloc[-1]

        if 'd' in data_frequency:
            return pd.Series([
                self._daily_bars[asset][field].iloc[-1]
                for asset in assets
            ], index=assets)
        else:
            return pd.Series([
                self._minutely_bars[asset][field].iloc[-1]
                for asset in assets
            ], index=assets)

    def get_bars(self, assets, data_frequency, bar_count=500):
        assets_is_scalar = not isinstance(assets, (list, set, tuple))
        if assets_is_scalar:
            assets = [assets]

        barslist = []

        for asset in assets:

            if 'm' in data_frequency:
                bars = self._minutely_bars[asset].copy()
            else:
                bars = self._daily_bars[asset].copy()

            bars.columns = pd.MultiIndex.from_product([[asset], bars.columns])

            barslist.append(bars[-bar_count:])

        return pd.concat(barslist, axis=1)

    @property
    def time_skew(self):
        return pd.Timedelta('0s')

    def all_orders(self, asset=None, before=None, status='all'):
        a1 = 'ASSET1'
        a2 = 'ASSET2'

        return {
            'o01': ZPOrder(
                dt=pd.Timestamp('2018-10-31 09:40:00-0400'),
                asset=a1,
                amount=2,
                id='o01',
            ),
            'o02': ZPOrder(
                dt=pd.Timestamp('2018-10-31 09:45:00-0400'),
                asset=a1,
                amount=5,
                id='o02',
            ),
            'o03': ZPOrder(
                dt=pd.Timestamp('2018-10-31 09:45:00-0400'),
                asset=a2,
                amount=3,
                id='o03',
            ),
        }

    def initialize_data(self, context):
        pass
