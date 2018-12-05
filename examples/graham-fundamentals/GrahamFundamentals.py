# This is an implementation of some of the stock-selection principles outlined here:
# https://cabotwealth.com/daily/value-investing/benjamin-grahams-value-stock-criteria/
# No guarantees are provided about the performance of these principles as described
# or as implemented here. As with any strategy, you should validate its performance
# with backtesting and forward testing before committing to its use.

# This algorithm select stocks from several sectors that fit its criteria for being a
# safe investment - it looks for companies who have relatively small PE and PB ratios,
# positive earnings per share, a dividend of at least 1%, and manageable near-term and
# long-term debt loads.

# It weights its investments in the stocks it finds by market cap, but such that each
# sector (with at least one acceptable stock) has an even amount of cash dedicated to it
# overall. It rebalances its selections and cash allocations once every three months.

from iexfinance.base import _IEXBase
from iexfinance import Stock
from urllib.parse import quote
from pylivetrader import *
import pandas as pd
import numpy as np
import json


def get_sector(sector_name):
    collection = SectorCollection(sector_name)
    return collection.fetch()


def initialize(context):
    # These are the sectors we're interested in trading.
    # They can be individually commented out if you wish to avoid one sector
    # or another.
    context.sectors = [
        'Basic Materials',
        'Consumer Cyclical',
        'Financial Services',
        'Real Estate',
        'Consumer Defensive',
        'Healthcare',
        'Utilities',
        'Communication Services',
        'Energy',
        'Industrials',
        'Technology'
    ]

    context.months_until_rebalance = 1
    schedule_function(try_rebalance,
                      date_rule=date_rules.month_start(),
                      time_rule=time_rules.market_open())
    context.run_once = True

def handle_data(context, data):
    # Go ahead and run once when the script starts to fill out the portfolio.
    if context.run_once:
        print("ordering")
        try_rebalance(context, data)
        context.run_once = False

def try_rebalance(context, data):
    # See if it's time to rebalance every month.
    # We'll reevaluate our positions once every three months.
    if context.months_until_rebalance == 1:
        update_target_securities(context)
        rebalance(context)
        context.months_until_rebalance = 3
    else:
        context.months_until_rebalance -= 1


def update_target_securities(context):
    # In order to avoid overinvestment in large sectors, we'll be weighting each
    # stock by its sector contribution. More on this below.
    context.total_sector_contributions = 0

    # First, we'll grab all the stocks in the sectors we want to trade within.
    sector_fundamental_dfs = {}
    for sector in context.sectors:
        fundamental_df = build_sector_fundamentals(sector)
        # fundamental_df = fundamental_df.sort_values(by=['market_cap'], ascending=False)
        filtered_fundamental_df = filter_fundamental_df(fundamental_df)

        # To weight by sector contribution, we'll first store each stock's
        # contribution to its own sector's presence in our portfolio as a
        # percentage.
        sector_market_cap = filtered_fundamental_df['market_cap'].sum()
        filtered_fundamental_df['sector_contribution'] = filtered_fundamental_df['market_cap'] / sector_market_cap

        # We'll add up all these percentage values, and our portfolio's weight
        # in a stock will be determined by its weight relative to the sum total
        # of all sector contributions.
        context.total_sector_contributions += filtered_fundamental_df['sector_contribution'].sum()
        sector_fundamental_dfs[sector] = filtered_fundamental_df

    # At this point, merge all our dataframes together, as we're done
    # considering sectors.
    context.all_sectors_fundamental_df = pd.concat(
        list(sector_fundamental_dfs.values()))


def rebalance(context):
    # We want to purchase all stocks in our dataframe, if possible.
    desired_stocks = context.all_sectors_fundamental_df.index.values
    print(desired_stocks)

    # Exit all positions we wish to drop before starting new ones.
    for stock in context.portfolio.positions:
        if stock.symbol not in desired_stocks:
            order_target_percent(stock, 0)

    # Rebalance all stocks to target weights.
    for stock in desired_stocks:
        # Determine how much of the portfolio should be allocated to this
        # stock.
        weight = get_weight(context, stock)
        print('weight: {}'.format(weight))
        if weight != 0:
            try:
                print('Buying {}'.format(stock))
                order_target_percent(symbol(stock), weight)
            except BaseException as e:
                print(
                    'Error: Tried to purchase {} but there was an error.'.format(stock))
                print(e)


def get_weight(context, stock):
    # As discussed above, we'll be weighting each stock by its contribution to
    # its sector.
    return context.all_sectors_fundamental_df.loc[stock]['sector_contribution'] / \
        context.total_sector_contributions


def filter_fundamental_df(fundamental_df):
    # This is where we remove stocks that don't meet our investment criteria.
    return fundamental_df[
        (fundamental_df.current_ratio > 1.5) &
        (fundamental_df.debt_to_liq_ratio < 1.1) &
        (fundamental_df.pe_ratio < 9) &
        (fundamental_df.pb_ratio < 1.2) &
        (fundamental_df.dividend_yield > 1.0)
    ]


def build_sector_fundamentals(sector):
    '''
    In this method, for the given sector, we'll get the data we need for each stock
    in the sector from IEX. Once we have the data, we'll check that the earnings
    reports meet our criteria with `eps_good()`. We'll put stocks that meet those
    requirements into a dataframe along with all the data about them we'll need.
    '''
    stocks = get_sector(sector)
    if len(stocks) == 0:
        raise ValueError("Invalid sector name: {}".format(sector))

    # If we can't see its PE here, we're probably not interested in a stock.
    # Omit it from batch queries.
    stocks = [s for s in stocks if s['peRatio'] is not None]

    # IEX doesn't like batch queries for more than 100 symbols at a time.
    # We need to build our fundamentals info iteratively.
    batch_idx = 0
    batch_size = 99
    fundamentals_dict = {}
    while batch_idx < len(stocks):
        symbol_batch = [s['symbol']
                        for s in stocks[batch_idx:batch_idx + batch_size]]
        stock_batch = Stock(symbol_batch)

        # Pull all the data we'll need from IEX.
        financials_json = stock_batch.get_financials()
        quote_json = stock_batch.get_quote()
        stats_json = stock_batch.get_key_stats()
        earnings_json = stock_batch.get_earnings()

        for symbol in symbol_batch:
            # We'll filter based on earnings first to keep our fundamentals
            # info a bit cleaner.
            if not eps_good(earnings_json[symbol]):
                continue

            # Make sure we have all the data we'll need for our filters for
            # this stock.
            if not data_quality_good(
                    symbol,
                    financials_json,
                    quote_json,
                    stats_json):
                continue

            fundamentals_dict[symbol] = get_fundamental_data_for_symbol(
                symbol,
                financials_json,
                quote_json,
                stats_json
            )

        batch_idx += batch_size
    # Transform all our data into a more filterable form - a dataframe - with
    # a bit of pandas magic.
    return pd.DataFrame.from_dict(fundamentals_dict).T


def eps_good(earnings_reports):
    # This method contains logic for filtering based on earnings reports.
    if len(earnings_reports) < 4:
        # The company must be very new. We'll skip it until it's had time to
        # prove itself.
        return False

    # earnings_reports should contain the information about the last four
    # quarterly reports.
    for report in earnings_reports:
        # We want to see consistent positive EPS.
        try:
            if not (report['actualEPS']):
                return False
            if report['actualEPS'] < 0:
                return False
        except KeyError:
            # A KeyError here indicates that some data was missing or that a company is
            # less than two years old. We don't mind skipping over new companies until
            # they've had more time in the market.
            return False
    return True


def data_quality_good(symbol, financials_json, quote_json, stats_json):
    # This method makes sure that we're not going to be investing in
    # securities we don't have accurate data for.

    if len(financials_json[symbol]
           ) < 1 or quote_json[symbol]['latestPrice'] is None:
        # No recent data was found. This can sometimes happen in case of recent
        # markert suspensions.
        return False

    try:
        if not (
            quote_json[symbol]['marketCap'] and
            stats_json[symbol]['priceToBook'] and
            stats_json[symbol]['sharesOutstanding'] and
            financials_json[symbol][0]['totalAssets'] and
            financials_json[symbol][0]['currentAssets'] and
            quote_json[symbol]['latestPrice']
        ):
            # Ignore companies IEX cannot report all necessary data for, or
            # thinks are untradable.
            return False
    except KeyError:
        # A KeyError here indicates that some data we need to evaluate this
        # stock was missing.
        return False

    return True


def get_fundamental_data_for_symbol(
        symbol,
        financials_json,
        quote_json,
        stats_json):
    fundamentals_dict_for_symbol = {}

    financials = financials_json[symbol][0]

    # Calculate PB ratio.
    fundamentals_dict_for_symbol['pb_ratio'] = stats_json[symbol]['priceToBook']

    # Find the "Current Ratio" - current assets to current debt.
    current_debt = financials['currentDebt'] if financials['currentDebt'] else 1
    fundamentals_dict_for_symbol['current_ratio'] = financials['currentAssets'] / current_debt

    # Find the ratio of long term debt to short-term liquiditable assets.
    total_debt = financials['totalDebt'] if financials['totalDebt'] else 0
    fundamentals_dict_for_symbol['debt_to_liq_ratio'] = total_debt / \
        financials['currentAssets']

    # Store other information for this stock so we can filter on the data
    # later.
    fundamentals_dict_for_symbol['pe_ratio'] = quote_json[symbol]['peRatio']
    fundamentals_dict_for_symbol['market_cap'] = quote_json[symbol]['marketCap']
    fundamentals_dict_for_symbol['dividend_yield'] = stats_json[symbol]['dividendYield']

    return fundamentals_dict_for_symbol


# We extend iexfinance a bit to support the sector collection endpoint.
class SectorCollection(_IEXBase):

    def __init__(self, sector, **kwargs):
        self.sector = quote(sector)
        self.output_format = 'json'
        super(SectorCollection, self).__init__(**kwargs)

    @property
    def url(self):
        return '/stock/market/collection/sector?collectionName={}'.format(
            self.sector)
