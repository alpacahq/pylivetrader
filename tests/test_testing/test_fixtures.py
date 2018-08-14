from pylivetrader.testing.fixtures import Backend as MockBackend


def test_mock_backend():

    m = MockBackend()

    assert len(m.get_equities()) == 3

    assets = m.get_equities()

    bars = m.get_bars([assets[0]], '1m')
    assert len(bars) == 500
    assert len(bars.columns) == 5

    bars = m.get_bars([assets[0]], '1d')
    assert len(bars) == 2
    assert len(bars.columns) == 5

    bars = m.get_bars(assets[:2], '1m')
    assert len(bars) == 500
    assert len(bars.columns) == 10
