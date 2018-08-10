from pylivetrader.assets import Asset


def test_asset():

    asset = Asset('asset-id', 'NSDQ', symbol='AAPL')

    assert asset.sid == 'asset-id'
    assert asset.symbol == 'AAPL'
    assert repr(asset) == 'Asset(asset-id, symbol=AAPL, exchange=NSDQ)'

    asset = Asset('asset-id', 'NSDQ', symbol='AAPL', asset_name='Apple, inc')
    assert repr(asset) == 'Asset(asset-id, symbol=AAPL,' \
        ' asset_name=Apple, inc, exchange=NSDQ)'
    assert asset.asset_name == 'Apple, inc'

    assert str(asset) == 'Asset(asset-id [AAPL])'

    # check rich comp
    asset2 = Asset('asset-id-2', 'NSDQ', symbol='NVDA')
    assert asset < asset2
