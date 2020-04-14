from pylivetrader.api import order_target, record, symbol
import pandas as pd

from logbook import Logger


log = Logger('macd-logger')
BUY_AMOUNT = 100


def initialize(context):
    # The initialize method is called at the very start of your script's
    # execution. You can set up anything you'll be needing later here. The
    # context argument will be received by all pylivetrader methods in
    # your script, and you can store information on it that you'd like to
    # share between methods.

    # This is the asset that we'll be trading.
    context.asset = symbol('AA')


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
    short_data = data.history(
        context.asset, 'price', bar_count=short_periods, frequency="1m")
    short_ema = pd.Series.ewm(short_data, span=short_periods).mean().iloc[-1]
    # Calculate long-term EMA (using data from the past 26 minutes.)
    long_periods = 26
    long_data = data.history(
        context.asset, 'price', bar_count=long_periods, frequency="1m")
    long_ema = pd.Series.ewm(long_data, span=long_periods).mean().iloc[-1]

    macd = short_ema - long_ema

    # Trading logic
    if macd > 0:
        # order_target_percent allocates a specified percentage of your
        # portfolio to a long position in a given asset. (A value of 1
        # means that 100% of your portfolio will be allocated.)
        order_id = order_target(context.asset, BUY_AMOUNT)
        if order_id:
            log.info("Bought {} shares of {}".format(BUY_AMOUNT,
                                                     context.asset.symbol))
    elif macd < 0:
        # You can supply a negative value to short an asset instead.
        order_id = order_target(context.asset, 0)
        if order_id:
            log.info("Closed position for {}".format(context.asset.symbol))

    # Save values for later inspection
    record(AA=data.current(context.asset, 'price'),
           short_mavg=short_ema,
           long_mavg=long_ema)
