from pylivetrader.protocol import Order

from pylivetrader.assets import Asset

from datetime import datetime


def test_order():
    asset = Asset('asset-id', 'NSDQ', symbol='AAPL')
    o = Order(dict(
        dt=datetime.now(),
        sid=asset,
        amount=3,
        filled=0,
    ))
    assert o.sid == asset
    assert o.amount == 3
