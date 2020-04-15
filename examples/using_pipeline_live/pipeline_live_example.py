from pylivetrader.api import order_target, record, symbol, order
import pandas as pd
from pipeline_live.data.alpaca.factors import AverageDollarVolume
from pipeline_live.data.alpaca.pricing import USEquityPricing
from pipeline_live.data.polygon.fundamentals import PolygonCompany
from zipline.pipeline import Pipeline
from logbook import Logger

log = Logger('pipeline-example-logger')
BUY_AMOUNT = 10


def initialize(context):
    # The initialize method is called at the very start of your script's
    # execution. You can set up anything you'll be needing later here. The
    # context argument will be received by all pylivetrader methods in
    # your script, and you can store information on it that you'd like to
    # share between methods.

    # let's create our pipeline and attach it to pylivetrader execution
    top5 = AverageDollarVolume(window_length=20).top(5)  # this is a filter
    context.pipe = Pipeline({
        'close':     USEquityPricing.close.latest,  # we only look at the close
        'marketcap': PolygonCompany.marketcap.latest,
    }, screen=top5)

    # this line connects to pylivetrader. this is done once, and we get a new
    # list of asset every day in before_trading_start()
    context.attach_pipeline(context.pipe, "pipe")


def before_trading_start(context, data):
    # this line will compute the pipeline for today's filtered assets
    context.output = context.pipeline_output('pipe')


def handle_data(context, data):
    # The handle_data method is called by pylivetrader every minute when
    # new data is received. This is where we'll execute our trading logic. For
    # an explanation of pylivetrader function scheduling, please see here:
    # https://github.com/alpacahq/pylivetrader#run.

    # Compute averages
    # data.history() will return a pandas dataframe with price information.
    # pandas' EWM method will give us our exponential moving averages.

    # Calculate short-term EMA (using data from the past 12 minutes.)
    short_periods = 12
    long_periods = 26

    for asset in context.portfolio.positions:
        short_data = data.history(
            asset, 'price', bar_count=short_periods, frequency="1m")
        short_ema = pd.Series.ewm(short_data, span=short_periods).mean().iloc[
            -1]
        # Calculate long-term EMA (using data from the past 26 minutes.)
        long_data = data.history(
            asset, 'price', bar_count=long_periods, frequency="1m")
        long_ema = pd.Series.ewm(long_data, span=long_periods).mean().iloc[-1]

        macd = short_ema - long_ema

        if macd < 0:
            # You can supply a negative value to short an asset instead.
            order_id = order_target(asset, 0)
            if order_id:
                log.info("Closed position for {}".format(asset.symbol))

    for asset in context.output.index:


        short_data = data.history(
            asset, 'price', bar_count=short_periods, frequency="1m")
        short_ema = pd.Series.ewm(short_data, span=short_periods).mean().iloc[-1]
        # Calculate long-term EMA (using data from the past 26 minutes.)
        long_data = data.history(
              asset, 'price', bar_count=long_periods, frequency="1m")
        long_ema = pd.Series.ewm(long_data, span=long_periods).mean().iloc[-1]

        macd = short_ema - long_ema

        # Trading logic
        if macd > 0:
            # order_target allocates a specified target shares
            # to a long position in a given asset.
            order_id = order_target(asset, BUY_AMOUNT)
            if order_id:
                log.info("Bought {} shares of {}".format(BUY_AMOUNT,
                                                         asset.symbol))

