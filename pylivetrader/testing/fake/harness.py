import pandas as pd
from trading_calendars import get_calendar
from unittest.mock import patch

from pylivetrader.algorithm import Algorithm
from pylivetrader.misc.api_context import LiveTraderAPI
from pylivetrader.testing.fake import clock, backend


def noop(*args, **kwargs):
    pass


def run_smoke(algo):
    be = backend.Backend()

    a = Algorithm(
        initialize=getattr(algo, 'initialize', noop),
        handle_data=getattr(algo, 'handle_data', noop),
        before_trading_start=getattr(algo, 'before_trading_start', noop),
        backend=be,
    )
    on_dt_changed = a.on_dt_changed

    def _on_dt_changed(dt):
        tm = dt.tz_convert('America/New_York')
        if tm.hour == 16 and tm.minute == 0:
            raise StopIteration()
        on_dt_changed(dt)

    a.on_dt_changed = _on_dt_changed

    def _pipeline_output(name):
        import numpy as np

        def mock_data(name, dtype, index):
            if dtype == np.dtype('bool'):
                return [True] * len(index)
            elif dtype == np.dtype('float'):
                return [0.5] * len(index)
            elif dtype == np.dtype('object'):
                return ['data'] * len(index)
            elif dtype == np.dtype('int'):
                return [1] * len(index)
        index = [
            a.symbol('A'),
            a.symbol('Z'),
        ]
        pipe = a._pipelines[name]
        fakedata = {
            name: mock_data(name, c.dtype, index)
            for name, c in pipe.columns.items()
        }
        return pd.DataFrame(fakedata, index=index)

    a.pipeline_output = _pipeline_output

    cal = get_calendar('NYSE')

    with LiveTraderAPI(a), \
            patch('pylivetrader.executor.executor.RealtimeClock') as rc:
        def make_clock(*args, **kwargs):
            prev_open = cal.previous_open(pd.Timestamp.now())
            fc = clock.FaketimeClock(
                init_time=prev_open - pd.Timedelta('1hour'))
            be.set_clock(fc)
            return fc
        rc.side_effect = make_clock

        be.set_position(
            'A', 10, 200,
        )
        try:
            a.run()
        except StopIteration:
            pass
