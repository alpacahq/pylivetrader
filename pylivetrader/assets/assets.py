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
# See the License for the specific language governing permissions and
# limitations under the License.

from trading_calendars import get_calendar
from functools import total_ordering


@total_ordering
class Asset:

    def __init__(self, sid, exchange, symbol="", asset_name="", **kwargs):
        self.sid = sid
        self.exchange = exchange
        self.symbol = symbol
        self.asset_name = asset_name

        self.start_date = kwargs.get('start_date')
        self.end_date = kwargs.get('end_date')
        self.first_traded = None
        self.auto_close_date = None
        self.exchange_full = None

    def __hash__(self):
        return hash(self.sid)

    def __str__(self):
        if self.symbol:
            return '{}({} [{}])'.format(
                type(self).__name__, self.sid, self.symbol)
        else:
            return '{}({})'.format(type(self).__name__, self.sid)

    def __lt__(self, other):
        return self.symbol < other.symbol

    def __eq__(self, other):
        if hasattr(other, 'sid'):
            return self.sid == other.sid
        return False

    def __repr__(self):

        attrs = ['symbol', 'asset_name', 'exchange']

        params = [
            '{}={}'.format(a, getattr(self, a))
            for a in attrs
            if getattr(self, a) is not None and getattr(self, a) != ""
        ]

        return 'Asset({}, {})'.format(self.sid, ", ".join(params))

    def to_dict(self):
        return {
            'sid': self.sid,
            'symbol': self.symbol,
            'asset_name': self.asset_name,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'first_traded': self.first_traded,
            'auto_close_date': self.auto_close_date,
            'exchange': self.exchange,
            'exchange_full': self.exchange_full,
        }

    def from_dict(cls, dic):
        return cls(**dic)

    def is_exchange_open(self, dt_minute):
        """
        Parameters
        ----------
        dt_minute: pd.Timestamp (UTC, tz-aware)
            The minute to check.

        Returns
        -------
        boolean: whether the asset's exchange is open at the given minute.
        """
        calendar = get_calendar(self.exchange)
        return calendar.is_open_on_minute(dt_minute)

    def is_alive_for_session(self, session_label):
        """
        Returns whether the asset is alive at the given dt.

        Parameters
        ----------
        session_label: pd.Timestamp
            The desired session label to check. (midnight UTC)

        Returns
        -------
        boolean: whether the asset is alive at the given dt.
        """
        ref_start = self.start_date.value
        ref_end = self.end_date.value

        return ref_start <= session_label.value <= ref_end


class Equity(Asset):
    pass
