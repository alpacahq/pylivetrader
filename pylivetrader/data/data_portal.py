from functools import lru_cache
from logbook import Logger
import pandas as pd

log = Logger('DataPortal')


class DataPortal:

    def __init__(self, broker, asset_finder, trading_calendar):
        self.broker = broker
        self.asset_finder = asset_finder
        self.trading_calendar = trading_calendar

    def get_last_traded_dt(self, asset, dt, data_frequency):
        return self.broker.get_last_traded_dt(asset)

    def get_adjusted_value(self, assets, field, dt, perspective_dt, data_frequency):
        '''
        TODO:
        for external data (fetch_csv) support, need to update logic here.
        '''
        return self.broker.get_spot_value(assets, field, dt, data_frequency)

    def get_spot_value(self, assets, field, dt, data_frequency):
        return self.broker.get_spot_value(assets, field, dt, data_frequency)

    @lru_cache(10)
    def _get_realtime_bars(self, assets, frequency, bar_count, end_dt):
        return self.broker.get_bars(
            assets, frequency, bar_count=bar_count)

    def cache_clear(self):
        return self._get_realtime_bars.cache_clear()

    def get_history_window(self,
                           assets,
                           end_dt,
                           bar_count,
                           frequency,
                           field,
                           data_frequency,
                           ffill=True):

        # convert list of asset to tuple of asset to be hashable
        assets = tuple(assets)

        # Broker.get_realtime_history() returns the asset as level 0 column,
        # open, high, low, close, volume returned as level 1 columns.
        # To filter for field the levels needs to be swapped
        bars = self._get_realtime_bars(assets, frequency, bar_count=bar_count, end_dt=end_dt).swaplevel(0, 1, axis=1)

        ohlcv_field = 'close' if field == 'price' else field

        bars = bars[ohlcv_field]

        if ffill and field == 'price':
            # Simple forward fill is not enough here as the last ingested
            # value might be outside of the requested time window. That case
            # the time series starts with NaN and forward filling won't help.
            # To provide values for such cases we backward fill.
            # Backward fill as a second operation will have no effect if the
            # forward-fill was successful.
            bars.fillna(method='ffill', inplace=True)
            bars.fillna(method='bfill', inplace=True)

        return bars[-bar_count:]
