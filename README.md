# pylivetrader

pylivetrader is a simple python live trading framework with zipline interface.

## Simple Usage

Here is the example dual moving average algorithm (by [quantopian/zipline](https://github.com/quantopian/zipline/blob/master/zipline/examples/dual_moving_average.py)). We provide mostly the same API interfaces with zipline.

```py
from pylivetrader.api import order_target, symbol

def initialize(context):
    context.i = 0
    context.asset = symbol('AAPL')

def handle_data(context, data):
    # Compute averages
    # data.history() has to be called with the same params
    # from above and returns a pandas dataframe.
    short_mavg = data.history(context.asset, 'price', bar_count=100, frequency="1m").mean()
    long_mavg = data.history(context.asset, 'price', bar_count=300, frequency="1m").mean()

    # Trading logic
    if short_mavg > long_mavg:
        # order_target orders as many shares as needed to
        # achieve the desired number of shares.
        order_target(context.asset, 100)
    elif short_mavg < long_mavg:
        order_target(context.asset, 0)
```

You can run your algorithm from CLI tool named `pylivetrader`, simply like below. Then your algorithm just start running with broker API. You don't need to ready for bundle file in advance as zipline does.

```sh
$ pylivetrader run -f algo.py --broker-config config.yaml
```

Config file is just simple yaml or json format.

```
$ cat config.yaml
key_id: BROKER_API_KEY
secret: BROKER_SECRET
```

## Installation

Install with pip.

```
$ pip install pylivetrader
```

## Supported Broker

### Alpaca

Configuration by environment variables.

```
$ export APCA_API_KEY_ID={your api key id}
$ export APCA_API_SECRET_KEY={your api secret key}
$ pylivetrader run -f algo.py
```

Configuration by config file. Either yaml or json.

```
$ cat config.yaml
key_id: {your api key id}
secret: {your api secret key}
$ pylivetrader run -f algo.py --broker-config config.yaml
```
