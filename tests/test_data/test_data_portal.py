import pandas as pd
from pylivetrader.testing.fixtures import get_fixture_data_portal


def test_data_portal():
    data_portal = get_fixture_data_portal()

    asset = data_portal.asset_finder.retrieve_asset('asset-0')

    values = data_portal.get_history_window(
        [asset], None, 10, '1m', 'price', 'minute')
    assert len(values) == 10

    last_in_fields = {
        'open': 780 + 10 - 1,
        'high': 780 + 15 - 1,
        'low': 780 + 8 - 1,
        'close': 780 + 10 - 1,
        'price': 780 + 10 - 1,
        'volume': 100,
    }

    fields = ['open', 'high', 'low', 'close', 'price', 'volume']
    for f in fields:

        values = data_portal.get_history_window(
            [asset], None, 10, '1m', f, 'minute')
        assert len(values) == 10

        values = data_portal.get_history_window(
            [asset], None, 1, '1d', f, 'day')
        assert len(values) == 1

        v = data_portal.get_spot_value(asset, f, None, '1m')
        assert v == last_in_fields[f]

        v = data_portal.get_spot_value([asset], f, None, '1m')
        assert type(v) == pd.Series
        assert v[asset] == last_in_fields[f]

    # cache_clear
    assert data_portal._get_realtime_bars.cache_info().currsize > 0
    data_portal.cache_clear()
    assert data_portal._get_realtime_bars.cache_info().currsize == 0
