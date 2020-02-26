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

from .alpaca import Backend as AlpacaBackend
from .alpaca import skip_http_error, NY

from pylivetrader.misc.parallel_utils import parallelize

import pandas as pd


class Backend(AlpacaBackend):
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

        # temp workaround for less bars after masking by
        # market hours
        query_limit = limit
        if query_limit is not None:
            query_limit *= 2

        @skip_http_error((404, 504))
        def fetch(symbol):
            pre_df = self._api.get_barset(
                symbol, size, query_limit, start=_from, end=to
            )
            df = pre_df[symbol].df
            if size == 'minute':
                df.index += pd.Timedelta('1min')
                # Avoid array out of bounds
                if not df.empty:
                    # Mask out bars outside market hours
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
        Query the Alpaca API in parallel for multiple symbols and
        return in dict.

        There is no last_trade in the Alpaca API, so it's loosely
        mimicked using the last bar available. For full volume and
        trade data, a Polygon or Alpaca brokerage account will be
        needed.

        symbols: list[str]

        return: dict[str -> dict[str->float]]
        '''

        @skip_http_error((404, 504))
        def fetch(symbol):
            # Extract the price and time from the last bar
            bars = self._api.get_barset(symbol, '1min', 1)[symbol]
            return {
                'price': bars[0].c,
                'timestamp': bars[0].t,
            }

        return parallelize(fetch)(symbols)

    def get_last_traded_dt(self, asset):
        # There's not a great way to mimic this without Polygon. If a strategy
        # needs this method, it probably needs the real version.
        raise Exception(
            'get_last_traded_dt is not supported by the paper-only backend'
        )

    def _get_spot_trade(self, symbols, field):
        if field == 'last_traded':
            # There's not a great way to mimic this without Polygon.
            # If a strategy needs this field, it probably needs the
            # real version.
            raise Exception(
                'last_traded is not supported by the paper-only backend'
            )
        self.super(symbols, field)
