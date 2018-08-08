

def handle_data(ctx, data):
    print('run handledata')

    print('## symbol')
    asset = symbol('AAPL')
    print(asset)

    print('## history')
    dat = data.history(symbol('AAPL'), 'price', 5, '1d')
    print(dat)
    dat = data.history(symbol('AAPL'), ['close', 'open'], 1, 'minute')
    print(dat)

    print('## current')
    dat = data.current(symbol('AAPL'), 'price')
    print(dat)

    print('## open')
    orders = get_open_orders()
    print(sum([len(s) for _, s in orders.items()]), 'opens')
    for order_asset, asset_orders in orders.items():
        for o in asset_orders:
            print('cancel', order_asset.symbol, o.id)
            cancel_order(o)

    print('## order')
    if data.can_trade(asset):
        oid = order(asset, 1)
    print('sent', oid)


def initialize(context):
    print('run initialize')

    schedule_function(
        run_on_market_open,
        date_rules.every_day(),
        time_rules.market_open(minutes=1)
    )


def run_on_market_open(context, data):

    print('run on market open')
