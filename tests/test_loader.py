from pylivetrader.loader import get_functions


def test_functions_01():
    # translate zipline to pylivetrader

    script = '''
from zipline.api import *
import zipline.api as api1
from zipline import api as api2

def handle_data(ctx, data):
    symbol('AAPL')
'''

    m = get_functions(script)
    assert 'handle_data' in m


def test_functions_02():
    # you don't need to import api

    script = '''
def handle_data(ctx, data):

    asset = symbol('AAPL')

    order(asset, 1)
'''

    m = get_functions(script)
    assert 'handle_data' in m
