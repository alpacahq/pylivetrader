import pandas as pd

from pylivetrader.assets import Asset


def test_asset():

    asset = Asset(
        'asset-id', 'NYSE',
        symbol='AAPL',
        start_date=pd.Timestamp('2018/08/13', tz='UTC'),
        end_date=pd.Timestamp('2018/08/18', tz='UTC'),
    )

    assert asset.sid == 'asset-id'
    assert asset.symbol == 'AAPL'
    assert repr(asset) == 'Asset(asset-id, symbol=AAPL, exchange=NYSE)'

    asset = Asset('asset-id', 'NYSE', symbol='AAPL', asset_name='Apple, inc')
    assert repr(asset) == 'Asset(asset-id, symbol=AAPL,' \
        ' asset_name=Apple, inc, exchange=NYSE)'
    assert asset.asset_name == 'Apple, inc'

    assert str(asset) == 'Asset(asset-id [AAPL])'

    # check rich comp
    asset2 = Asset('asset-id-2', 'NYSE', symbol='NVDA')
    assert asset < asset2

    sorted_assets = sorted([asset2, asset])
    assert sorted_assets[0] == asset

    assert not asset == 'invalid'

    # is_exchange_open
    asset = Asset(
        'asset-id', 'NYSE',
        symbol='AAPL',
        start_date=pd.Timestamp('2018/08/13', tz='UTC'),
        end_date=pd.Timestamp('2018/08/18', tz='UTC'),
    )

    before_market_open = pd.Timestamp(
        '2018/08/13 08:00', tz='America/New_York').tz_convert('UTC')
    assert not asset.is_exchange_open(before_market_open)

    open = pd.Timestamp(
        '2018/08/13 13:00', tz='America/New_York').tz_convert('UTC')
    assert asset.is_exchange_open(open)

    after_market_close = pd.Timestamp(
        '2018/08/13 16:01', tz='America/New_York').tz_convert('UTC')
    assert not asset.is_exchange_open(after_market_close)

    # is_alive_for_session

    assert asset.is_alive_for_session(pd.Timestamp('2018/08/13', tz='UTC'))

    assert not asset.is_alive_for_session(pd.Timestamp('2018/08/10', tz='UTC'))
