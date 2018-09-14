import numpy as np
import pandas as pd
from unittest.mock import patch

from pylivetrader.algorithm import Algorithm
from pylivetrader.misc.api_context import LiveTraderAPI
from . import clock, backend


def mock_data(name, dtype, index):
    if dtype == np.dtype('bool'):
        return [True] * len(index)
    elif dtype == np.dtype('float'):
        return [0.5] * len(index)
    elif dtype == np.dtype('object'):
        return ['data'] * len(index)
    elif dtype == np.dtype('int'):
        return [1] * len(index)


class DefaultPipelineHooker:

    def __init__(self):
        pass

    def output(self, context, name):

        pipe = context._pipelines[name]

        index = [
            context.symbol('A'),
            context.symbol('Z'),
        ]
        fakedata = {
            name: mock_data(name, c.dtype, index)
            for name, c in pipe.columns.items()
        }
        return pd.DataFrame(fakedata, index=index)


def noop(*args, **kwargs):
    pass


def run_smoke(algo, before_run_hook=None, pipeline_hook=None):
    fake_clock = clock.FaketimeClock()
    # fake_clock.rollback(1)
    be = backend.Backend(clock=fake_clock)

    a = Algorithm(
        initialize=getattr(algo, 'initialize', noop),
        handle_data=getattr(algo, 'handle_data', noop),
        before_trading_start=getattr(algo, 'before_trading_start', noop),
        backend=be,
    )

    if pipeline_hook is not None:
        def _pipeline_output(name):
            return pipeline_hook.output(a, name)

        a.pipeline_output = _pipeline_output

    with LiveTraderAPI(a), \
            patch('pylivetrader.executor.executor.RealtimeClock') as rc:
        def make_clock(*args, **kwargs):
            # may want to reconfigure clock
            return fake_clock
        rc.side_effect = make_clock

        if before_run_hook is not None:
            before_run_hook(a, be)
        a.run()
