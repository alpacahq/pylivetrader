from pylivetrader import protocol as proto
from pylivetrader.finance.order import Order
from pylivetrader.assets import Asset

from datetime import datetime


def test_order():

    asset = Asset('asset-id', 'NSDQ', symbol='AAPL')

    o = Order(datetime.now(), asset, 3)
    assert o.asset == asset
    assert o.sid == asset
    assert o.open

    o.filled = 3
    assert o.open_amount == 0
    assert not o.open

    assert type(o.to_api_obj()) == proto.Order
