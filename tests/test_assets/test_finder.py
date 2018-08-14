import pytest

from pylivetrader.assets import Equity, AssetFinder
from pylivetrader.errors import SidsNotFound, SymbolNotFound, EquitiesNotFound


def test_finder():
    asset = Equity('asset-id', 'NSDQ', symbol='AAPL')

    class DummyBroker:

        def get_equities(self):
            return [asset]

    # retrieve_asset
    finder = AssetFinder(DummyBroker())
    assert finder.retrieve_asset('asset-id') == asset

    with pytest.raises(SidsNotFound):
        finder.retrieve_asset('invalid')

    # retrieve_all
    assert finder.retrieve_all(['asset-id']) == [asset]

    with pytest.raises(SidsNotFound):
        assert finder.retrieve_all(['asset-id', 'invalid'])

    assert finder.retrieve_all(['asset-id', 'invalid'], default_none=True) \
        == [asset, None]

    # retrieve_equities
    assert finder.retrieve_equities(['asset-id'])['asset-id'] == asset
    with pytest.raises(EquitiesNotFound):
        assert finder.retrieve_equities(['inv'])

    # asset should be cached until cleared
    assert hasattr(finder, 'asset_cache')

    finder.clear_cache()
    assert not hasattr(finder, 'asset_cache')

    # lookup_symbol

    assert finder.lookup_symbol('AAPL', None) == asset
    assert finder.lookup_symbol('AAPL', None, fuzzy=True) == asset

    with pytest.raises(SymbolNotFound):
        finder.lookup_symbol('invalid', None)

    with pytest.raises(SymbolNotFound):
        finder.lookup_symbol('invalid', None, fuzzy=True)

    # lookup_symbols

    assert finder.lookup_symbols(['AAPL'], None) == [asset]
    assert finder.lookup_symbols(['AAPL'], None, fuzzy=True) == [asset]

    with pytest.raises(SymbolNotFound):
        finder.lookup_symbols(['AAPL', 'invalid'], None)

    with pytest.raises(SymbolNotFound):
        finder.lookup_symbols(['AAPL', 'invalid'], None)

    # sids
    assert finder.sids == ['asset-id']
