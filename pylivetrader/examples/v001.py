from zipline.api import symbol, sid


def handle_data(ctx, data):
    print('run handledata')

    print(symbol('AAPL'))


def initialize(context):

    print('run initialize')
