import pandas as pd
from unittest.mock import patch

from pylivetrader.algorithm import Algorithm
from pylivetrader.misc.api_context import LiveTraderAPI
from pylivetrader.testing.fake import clock, backend


def noop(*args, **kwargs):
    pass


def run_smoke(algo):
    fake_clock = clock.FaketimeClock()
    # fake_clock.rollback(1)
    be = backend.Backend(clock=fake_clock)

    a = Algorithm(
        initialize=getattr(algo, 'initialize', noop),
        handle_data=getattr(algo, 'handle_data', noop),
        before_trading_start=getattr(algo, 'before_trading_start', noop),
        backend=be,
    )

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

    with LiveTraderAPI(a), \
            patch('pylivetrader.executor.executor.RealtimeClock') as rc:
        def make_clock(*args, **kwargs):
            # may want to reconfigure clock
            return fake_clock
        rc.side_effect = make_clock

        be.set_position(
            'A', 10, 200,
        )
        a.run()
