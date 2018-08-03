import pytest

import pylivetrader.api as api


def test_basic_api_call():

    with pytest.raises(RuntimeError) as e:

        api.symbol('AAPL')

    assert 'must be callled during live trading' in str(e)
