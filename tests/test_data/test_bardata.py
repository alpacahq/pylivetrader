import pandas as pd

from pylivetrader.assets import Asset
from pylivetrader.data.bardata import BarData
from pylivetrader.testing.fixtures import get_fixture_data_portal


def test_bardata():
    portal = get_fixture_data_portal()

    asset0 = portal.asset_finder.retrieve_asset('asset-0')
    asset1 = portal.asset_finder.retrieve_asset('asset-1')

    data = BarData(portal, 'minute')

    # current

    last_in_fields = {
        'open': 780 + 10 - 1,
        'high': 780 + 15 - 1,
        'low': 780 + 8 - 1,
        'close': 780 + 10 - 1,
        'price': 780 + 10 - 1,
        'volume': 100,
    }

    for k, v in last_in_fields.items():

        assert data.current(asset0, k) == v

        o = data.current([asset0, asset1], k)
        assert len(o) == 2
        assert type(o) == pd.Series

    o = data.current(asset0, ['open', 'close'])
    assert len(o) == 2
    assert type(o) == pd.Series

    o = data.current([asset0, asset1], ['open', 'close'])
    assert set(list(o.columns)) == set(['open', 'close'])
    assert set(list(o.index)) == set([asset0, asset1])

    # history
    day_values = {
        'open': 2 + 10 - 1,
        'high': 2 + 15 - 1,
        'low': 2 + 8 - 1,
        'close': 2 + 10 - 1,
        'price': 2 + 10 - 1,
        'volume': 100,
    }

    for k, v in last_in_fields.items():

        assert data.history(asset0, k, 1, 'minute').iloc[0] == v
        assert data.history(asset0, k, 1, 'day').iloc[0] == day_values[k]

    o = data.history([asset0, asset1], 'open', 1, 'minute')
    assert type(o) == pd.DataFrame
    assert len(o.index) == 1
    assert len(o.columns) == 2

    o = data.history([asset0, asset1], ['open', 'close'], 1, 'minute')
    assert type(o) == pd.Panel

    # can_trade
    data.datetime = pd.Timestamp('2018-08-13', tz='UTC')

    asset_to_check = Asset(
        'asset-0', 'NYSE', symbol='ASSET',
        start_date=pd.Timestamp('2018-01-01', tz='UTC'),
        end_date=pd.Timestamp('2018/08/13', tz='UTC'),
    )
    assert data.can_trade(asset_to_check)
    assert not data.is_stale(asset_to_check)

    # data.datetime = pd.Timestamp('2018-08-14', tz='UTC')
    # assert not data.can_trade(asset_to_check)
    # when asset is not tradable, return false
    assert not data.is_stale(asset_to_check)
