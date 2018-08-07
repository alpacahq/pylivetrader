from zipline.api import *


def handle_data(ctx, data):
    print('run handledata')

    print('## symbol')
    asset = symbol('AAPL')
    print(asset)

    print('## history')
    dat = data.history(symbol('AAPL'), 'price', 1, '1d')
    print(dat)
    dat = data.history(symbol('AAPL'), ['close', 'open'], 1, 'minute')
    print(dat)

    print('## current')
    dat = data.current(symbol('AAPL'), 'price')
    print(dat)

    print('## order')
    oid = order(asset, 1)
    print('sent', oid)

def initialize(context):

    print('run initialize')
