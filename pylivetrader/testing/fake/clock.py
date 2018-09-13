from time import sleep

from logbook import Logger
import pandas as pd
from trading_calendars import get_calendar

BAR = 0
SESSION_START = 1
SESSION_END = 2
MINUTE_END = 3
BEFORE_TRADING_START_BAR = 4


log = Logger('Realtime Clock')


class FaketimeClock(object):

    def __init__(self,
                 calendar=None,
                 before_trading_start_minute=(pd.Timestamp('8:45').time(), 'America/New_York'),
                 minute_emission=True,
                 time_skew=None,
                 init_time=None,
                ):
        self.calendar = calendar or get_calendar('NYSE')
        self.before_trading_start_minute = before_trading_start_minute
        self.minute_emission = minute_emission
        self._last_emit = None
        self._before_trading_start_bar_yielded = False
        self._current_time = init_time.floor('1min') if init_time is not None else pd.Timestamp.utcnow()

    @property
    def now(self):
        return self._current_time.tz_convert('America/New_York')

    def _next(self):
        self._current_time += pd.Timedelta('1min')
        return self._current_time

    def __iter__(self):

        current_session = None

        while True:
            server_time = self._next()

            session_label = server_time.floor('1D')
            if not self.calendar.is_session(session_label):
                # wait until next session
                # sleep(1)
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
                pass
                # sleep(1)
            elif (session_open <= server_time < session_close):
                if (self._last_emit is None or
                        server_time - self._last_emit >=
                        pd.Timedelta('1 minute')):
                    self._last_emit = server_time
                    yield server_time, BAR
                    if self.minute_emission:
                        yield server_time, MINUTE_END
                else:
                    # sleep(1)
                    pass
            elif server_time == session_close:
                self._last_emit = server_time
                yield server_time, BAR
                if self.minute_emission:
                    yield server_time, MINUTE_END
                yield server_time, SESSION_END
            elif server_time > session_close:
                # sleep(1)
                pass
            else:
                # We should never end up in this branch
                raise RuntimeError("Invalid state in RealtimeClock")
