#
# Copyright https://github.com/zipline-live/zipline
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

from time import sleep

from logbook import Logger
import pandas as pd

BAR = 0
SESSION_START = 1
SESSION_END = 2
MINUTE_END = 3
BEFORE_TRADING_START_BAR = 4


log = Logger('Realtime Clock')


class RealtimeClock(object):
    """Realtime clock for live trading.

    This class is a drop-in replacement for
    :class:`zipline.gens.sim_engine.MinuteSimulationClock`.
    The key difference between the two is that the RealtimeClock's event
    emission is synchronized to the (broker's) wall time clock, while
    MinuteSimulationClock yields a new event on every iteration (regardless of
    wall clock).

    The :param:`time_skew` parameter represents the time difference between
    the Broker and the live trading machine's clock.
    """

    def __init__(self,
                 calendar,
                 before_trading_start_minute,
                 minute_emission,
                 time_skew=pd.Timedelta("0s"),
                 is_broker_alive=None):
        self.calendar = calendar
        self.before_trading_start_minute = before_trading_start_minute
        self.minute_emission = minute_emission
        self.time_skew = time_skew
        self.is_broker_alive = is_broker_alive or (lambda: True)
        self._last_emit = None
        self._before_trading_start_bar_yielded = False

    def __iter__(self):

        current_session = None

        while True:
            current_time = pd.to_datetime('now', utc=True)
            server_time = (current_time + self.time_skew).floor('1 min')

            session_label = server_time.floor('1D')
            if not self.calendar.is_session(session_label):
                # wait until next session
                sleep(1)
                continue

            if current_session is None or current_session != session_label:
                yield session_label, SESSION_START
                current_session = session_label
                self._before_trading_start_bar_yielded = False

            delta = pd.Timedelta(
                hours=self.before_trading_start_minute[0].hour,
                minutes=self.before_trading_start_minute[0].minute,
            )

            before_trading_start = (
                current_session
                .tz_localize(None)
                .tz_localize(self.before_trading_start_minute[1])
            ) + delta

            session_open = self.calendar.session_open(current_session)
            session_close = self.calendar.session_close(current_session)

            if (server_time >= before_trading_start and
                    not self._before_trading_start_bar_yielded):
                self._last_emit = server_time
                self._before_trading_start_bar_yielded = True
                yield server_time, BEFORE_TRADING_START_BAR
            elif server_time < session_open:
                sleep(1)
            elif (session_open <= server_time < session_close):
                if (self._last_emit is None or
                        server_time - self._last_emit >=
                        pd.Timedelta('1 minute')):
                    self._last_emit = server_time
                    yield server_time, BAR
                    if self.minute_emission:
                        yield server_time, MINUTE_END
                else:
                    sleep(1)
            elif server_time == session_close:
                self._last_emit = server_time
                yield server_time, BAR
                if self.minute_emission:
                    yield server_time, MINUTE_END
                yield server_time, SESSION_END
            elif server_time > session_close:
                sleep(1)
            else:
                # We should never end up in this branch
                raise RuntimeError("Invalid state in RealtimeClock")
