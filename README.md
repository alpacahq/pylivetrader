[![PyPI version](https://badge.fury.io/py/pylivetrader.svg)](https://badge.fury.io/py/pylivetrader)
[![CircleCI](https://circleci.com/gh/alpacahq/pylivetrader.svg?style=shield)](https://circleci.com/gh/alpacahq/pylivetrader)
[![Updates](https://pyup.io/repos/github/alpacahq/pylivetrader/shield.svg)](https://pyup.io/repos/github/alpacahq/pylivetrader/)
[![Python 3](https://pyup.io/repos/github/alpacahq/pylivetrader/python-3-shield.svg)](https://pyup.io/repos/github/alpacahq/pylivetrader/)

# pylivetrader

pylivetrader is a simple python live trading framework with zipline interface.
The main purpose is to run algorithms developed in the Quantopian platform in
live trading via broker API. In order to convert your algorithm for pylivetrader,
please read the [migration document](./migration.md).

## example code
check out the [examples](https://github.com/alpacahq/pylivetrader/tree/master/examples) 
folder. you will find there the following examples:
* simple MACD "momentum" trading
* using pipeline-live to screen top stocks every day
* a potfolio optimizer (used to optimize an existing porfolio. not to buy new
 stocks)
 
each sample code contains a readme file and a smoke runner (read further to
  understand what smoke is)

## Simple Usage

Here is the example dual moving average algorithm (by 
[quantopian/zipline](https://github.com/quantopian/zipline/blob/master/zipline/examples/dual_moving_average.py)).
 We provide mostly the same API interfaces with zipline.

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

You can run your algorithm from the CLI tool named `pylivetrader`, simply
like below. Then your algorithm starts running with broker API.
You don't need the data bundle file in advance unlike zipline does.

```sh
$ pylivetrader run -f algo.py --backend-config config.yaml
```

Config file is just simple yaml or json format.

```
$ cat config.yaml
key_id: BROKER_API_KEY
secret: BROKER_SECRET
base_url: https://paper-api.alpaca.markets
use_polygon: false
```
*note: we use the alpaca data api by default, you could change that by
 setting usePolygon to true.<br>
### Usage with redis

If you are running pylivetrader in an environment with an ephemeral file store and need your context
to persist across restarts, you can use the redis storage engine. This is useful if you launch in a
place like heroku.

To use this, you must install the redis-py library.

```sh
$ pip install redis
```

After that everything is the same as above, except the `run` command looks like the following:

```sh
$ pylivetrader run -f algo.py --backend-config config.yaml --storage-engine redis
```

Assuming you have redis running, this will now serialize your context object to and from redis.

## Installation

Install with pip. **pylivetrader currently supports only Python 3.6.

```
$ python3.6 -m venv venv
$ source venv/bin/activate
(venv)$ pip install pylivetrader
```

Additionally, pylivetrader works well with [pipeline-live](https://github.com/alpacahq/pipeline-live).

## Command Reference

### run

`pylivetrader run` starts live trading using your algorithm script. It starts
by calling the `initialize()` function if any, and waits until the market opens.
It calls the `before_trading_start` function if it is 8:45 ET (45 minutes
before the session starts) or if it starts after that. Once the session
starts, it calls the `handle_data()` function every minute until the
session ends, or any functions that are registered by `schedule_function` API.

The options are as follows

- `-f` or `--file`: the file path to the algorithm source
- `-b` or `--backend`: the name of backend to use
- `--backend-config`: the yaml file for backend parameters
- `--storage-engine`: the storage engine to use for persisting the context. ('file' or 'redis')
- `-s` or `--statefile`: the file path to the persisted state file (look for the State Management section below)
- `-r` or `--retry`: the algorithm runner continues execution in the event a general exception is raised
- `-l` or `--log-level`: the minimum level of log which will be written ('DEBUG', 'INFO', 'WARNING', 'ERROR', or 'CRITICAL')

### shell

`pylivetrader shell` goes into the IPython interactive shell mode as if you are
in the algorithm script namespace. It means, you can call Algorithm API
such as `symbol()` and `data.history()` so you can check the behavior
of each operation.

```
$ pylivetrader shell algo.py
```


The options are as follows

- `-f` or `--file`: the file path to the algorithm source
- `-b` or `--backend`: the name of backend to use
- `--backend-config`: the yaml file for backend parameters

#### things you could do with the shell
* get asset price data. e.g: data.history(symbol("AAPL"), "close", 10, "1d")
* check if you can trade a certain asset. e.g: data.can_trade(symbol("AAPL"))
* get your account information: context.account
* get your portfolio information: context.account.portfolio
* get all opened orders: context.get_open_orders()
* get all orders: context.get_all_orders()
* get a list of all available assets. eg: context._backend._api.list_assets(asset_class='us_equity')

### migrate

`pylivetrader migrate` allows you to easily migrate your quantopian/zipline code to pylivetrader compatible code.<br>
how to run:
```sh
pylivetrader migrate -i zipline_code.py -o pylivetrader_compatible.py
```
now you could execute it with the `run` command
<br>note: we do not support the optimize api by quantopian since it is not a part of zipline

## Working with Pipline-live
You can see an example usage under the examples folder.<br>
To work with pipeline-live you need to do the following steps:
* Create the pipeline (usually you will create it in a method, convention name is `make_pipeline()`. Inside you will define your universe and add factors and filters.
* DO NOT store the pipe in the context object. We cannot store it to the statefile and you don't need to do it. we store it for you.
* attach the pipeline to the Algortihm instance. do it like this: `context.attach_pipeline(pipe, "my_pipe")`. this should be done in the `intialize()` or `before_trading_start()` methods.
* Now, to get the output of the pipeline, you do this: `context.pipeline_output('my_pipe')`. you should call it in `handle_data()` or any other method you use the scheduler for.

## State Management

One of the things you need to understand in live trading is that things can
happen and you may need to restart the script or the program dies in the middle
of process due to some external errors. There are couple of things
to know in advance.

First, pylivetrader saves the property fields to the disk that you add to
the `context` object. It is stored in the pickle format and will be
restored on the next startup.

Second, because the context properties are restored, you may need to
take care of the extra steps. Often an algorithm is written under
the assumption that `initialize()` is called only once and
`before_trading_start()` is called once every morning. If you are
to restart the program in the middle of day, these functions are
called again, with the restored context object. Therefore, you
might need to check if the fields are from the other session
or in the same session to make sure you don't override the
indermediate states in the day.

## Supported Brokers

### Alpaca

Configuration by environment variables.

```
$ export APCA_API_KEY_ID={your api key id}
$ export APCA_API_SECRET_KEY={your api secret key}
$ export APCA_API_BASE_URL={https://api.alpaca.markets/ or https://paper-api.alpaca.markets}
$ pylivetrader run -f algo.py
```

Configuration by config file. Either yaml or json.

```
$ cat config.yaml
key_id: {your api key id}
secret: {your api secret key}
base_url: {https://api.alpaca.markets/ or https://paper-api.alpaca.markets}
$ pylivetrader run -f algo.py --backend-config config.yaml
```

## Docker

If you are already familiar with Docker, it is a good idea to
try our [docker image `alpacamarkets/pylivetrader`](https://hub.docker.com/r/alpacamarkets/pylivetrader/).
This has installed pylivetrader so you can start right away without
worrying about your python environment.  See more details in the
`dockerfiles` directory.
<br>If your algorithm file is called `algo.py`, this could be all you need to run it.

```sh
docker run -v $PWD:/work -w /work alpacamarkets/pylivetrader pylivetrader run -f algo.py
```

Make sure you set up environment variables for the backend
(use `-e KEY=VAL` for docker command).


you could also build the docker image from source like this:<br>
`docker build -t alpaca/pylivetrader-dev -f dockerfiles/Dockerfile-dev .`<br>
it gives you the power to run it locally and edit or debug the code if you desire.

## Smoke Test

pylivetrader provides a facility for smoke testing. This helps catch
issues such as typos, program errors and simple oversights. The following
is an example of smoke testing.

```py
import algo

from pylivetrader.testing.smoke import harness


def before_run(context, backend):
    '''This hook is called before algorithm starts.'''

    # Populate existing position
    backend.set_position(
        'A', 10, 200,
    )

    # modify some fields of context after `initialize(context)` is called
    _init = context._initialize
    def wrapper(ctx):
        _init(ctx)
        ctx.age[ctx.symbol('A')] = 3
        ctx.age[ctx.symbol('B')] = 2

    context._initialize = wrapper

def test_algo():
    pipeline = harness.DefaultPipelineHooker()

    # run the algorithm under the simulation environment
    harness.run_smoke(algo,
        before_run_hook=before_run,
        pipeline_hook=pipeline,
    )


if __name__ == '__main__':
    import logging
    logging.basicConfig(level=logging.DEBUG)
    test_algo()
```

This exercises the algorithm code by harnessing synthetic backend and price data.
The `pylivetrader.testing.smoke` package provides the backend and simulator
clock classes so that it simulates a market day from open to close.

By default, the backend creates a universe with 50 stocks ('A' .. 'AX').
For each symbol, you can query synthetic historical price, and orders
are managed within this simulator without having to set up a real remote
backend API. Additionally, you can hook up a couple of code injection
points such as `before_run_hook` and `pipeline_hook`. In this example,
the setup code creates a pre-populated position in the backend so you can
test the algorithm code path that accepts existing positions.

A `DefaultPipelineHooker` instance can return a synthetic pipeline result
with the same column names/types, inferred from the pipeline object
given in the `attach_pipeline` API.

Again, the purpose of this smoke testing is to actually exercise various
code paths to make sure there are no easy mistakes. This code works well
with standard test frameworks such as `pytest` and you can easily report
line coverage using those frameworks too.

## Running Multiple Strategies
There's a way to execute more than one algorithm at once.<br>
The websocket connection is limited to 1 connection per account. <br>
For that exact purpose this ![project](https://github.com/shlomikushchi/alpaca-proxy-agent)  was created<br>
The steps to execute this are:
* Run the Alpaca Proxy Agent as described in the project's README
* Define this env variable: `DATA_PROXY_WS` to be the address of the proxy agent. (e.g: `DATA_PROXY_WS=ws://192.168.99.100:8765`)
* execute your algorithm. it will connect to the servers through the proxy agent allowing you to execute multiple strategies

