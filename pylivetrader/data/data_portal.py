#
# Copyright 2016 Quantopian, Inc.
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
# See the License for the specific la

from functools import lru_cache
from logbook import Logger
import math

log = Logger('DataPortal')


class DataPortal:

    def __init__(
            self,
            backend,
            asset_finder,
            trading_calendar,
            quantopian_compatible):
        self.backend = backend
        self.asset_finder = asset_finder
        self.trading_calendar = trading_calendar
        self.quantopian_compatible = quantopian_compatible

    def get_last_traded_dt(self, asset, dt, data_frequency):
        return self.backend.get_last_traded_dt(asset)

    def get_adjusted_value(
            self,
            assets,
            field,
            dt,
            perspective_dt,
            data_frequency):
        '''
        TODO:
        for external data (fetch_csv) support, need to update logic here.
        '''
        return self.backend.get_spot_value(
            assets, field, dt, data_frequency, self.quantopian_compatible
        )

    def get_spot_value(self, assets, field, dt, data_frequency):
        return self.backend.get_spot_value(
            assets, field, dt, data_frequency, self.quantopian_compatible
        )

    @lru_cache(10)
    def _get_realtime_bars(self, assets, frequency, bar_count, end_dt):
        return self.backend.get_bars(
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

        # Backend.get_bars() returns the asset as level 0 column,
        # open, high, low, close, volume returned as level 1 columns.
        # To filter for field the levels needs to be swapped
        bars = self._get_realtime_bars(
            assets,
            frequency,
            bar_count=bar_count,
            end_dt=end_dt).swaplevel(
            0,
            1,
            axis=1)

        ohlcv_field = 'close' if field == 'price' else field

        if self.quantopian_compatible:
            # Quantopian seems to be less willing to return NaN values for
            # prices. If small bar counts are being requested, all the values
            # may be NaN. In order to more closely match their behavior, we
            # attempt to look back a few times. This is disabled when not in
            # compatibility mode in order to give the user more control over
            # how they handle missing data.
            for asset in assets:
                retry_count = 1
                while (all(math.isnan(bar) for bar in bars[ohlcv_field][asset])
                        and retry_count < 3):
                    retry_count += 1
                    bars = self._get_realtime_bars(
                        assets,
                        frequency,
                        bar_count=bar_count * retry_count,
                        end_dt=end_dt).swaplevel(
                        0,
                        1,
                        axis=1)

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
