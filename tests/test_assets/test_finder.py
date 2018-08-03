import pytest

from pylivetrader.assets import Asset, Equity, AssetFinder
from pylivetrader.errors import SidsNotFound


def test_finder():
    asset = Equity('asset-id', 'NSDQ', symbol='AAPL')

    class DummyBroker:

        def get_equities(self):
            return [asset]

    finder = AssetFinder(DummyBroker())
    assert finder.retrieve_asset('asset-id') == asset

    with pytest.raises(SidsNotFound):
        finder.retrieve_asset('invalid')
