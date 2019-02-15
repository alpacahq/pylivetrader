#
# Copyright 2015 Quantopian, Inc.
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

import datetime
from contextlib import ExitStack
from logbook import Logger

from pylivetrader.executor.realtimeclock import (
    RealtimeClock,
    BAR, SESSION_START, BEFORE_TRADING_START_BAR
)
from pylivetrader.data.bardata import BarData
from pylivetrader.misc.api_context import LiveTraderAPI

log = Logger('Executor')


class AlgorithmExecutor:

    def __init__(self, algo, data_portal):

        self.data_portal = data_portal
        self.algo = algo

        # This object is the way that user algorithms interact with OHLCV data,
        # fetcher data, and some API methods like `data.can_trade`.
        self.current_data = BarData(
            data_portal,
            self.algo.data_frequency,
        )

        before_trading_start_minute = \
            (datetime.time(8, 45), 'America/New_York')

        self.clock = RealtimeClock(
            self.algo.trading_calendar,
            before_trading_start_minute,
            minute_emission=algo.data_frequency == 'minute',
            time_skew=self.algo._backend.time_skew,
        )

    def run(self, retry=True):

        algo = self.algo

        def handle_retry(func):

            # decorator to log but swallow exception
            # if it is turned on. This is applied
            # only for periodic event. before_trading_start
            # is too critical to skip exception.
            def wrapper(*args, **kwargs):
                try:
                    func(*args, **kwargs)
                except Exception as exc:
                    if not retry:
                        raise
                    log.exception(exc)
                    log.warning('Continuing execution')

            return wrapper

        @handle_retry
        def every_bar(dt_to_use, current_data=self.current_data,
                      handle_data=algo.event_manager.handle_data):

            # clear data portal cache.
            self.data_portal.cache_clear()

            # called every tick (minute or day).
            algo.on_dt_changed(dt_to_use)

            self.current_data.datetime = dt_to_use

            handle_data(algo, current_data, dt_to_use)

            algo.portfolio_needs_update = True

        def once_a_day(midnight_dt, current_data=self.current_data,
                       data_portal=self.data_portal):

            # set all the timestamps
            algo.on_dt_changed(midnight_dt)
            self.current_data.datetime = midnight_dt

        def on_exit():
            # Remove references to algo, data portal, et al to break cycles
            # and ensure deterministic cleanup of these objects when the
            # simulation finishes.
            self.algo = None
            self.current_data = self.data_portal = None

        with ExitStack() as stack:
            stack.callback(on_exit)
            stack.enter_context(LiveTraderAPI(self.algo))

            # runs forever
            for dt, action in self.clock:
                if action == BAR:
                    every_bar(dt)
                elif action == SESSION_START:
                    once_a_day(dt)
                elif action == BEFORE_TRADING_START_BAR:
                    algo.on_dt_changed(dt)
                    self.current_data.datetime = dt
                    algo.before_trading_start(self.current_data)
