# This is an adaptation of Bruce Carroll's algorithm.
#   Algorithm's initial publication:
#   https://www.quantopian.com/posts/grahamfundmantals-algo-simple-screening-on-benjamin-graham-number-fundamentals
# It finds the two sectors with the lowest average P/E ratio among their top companies.
# Then, it buys stocks with low P/E and P/B ratios which do not have more current debt than current assets.
# Fundamentals data has been sourced from IEX, which gets its information from published balance sheets.

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

# Extend iexfinance to support the sector collection endpoint.
class SectorCollection(_IEXBase):

    def __init__(self, sector, **kwargs):
        self.sector = quote(sector)
        self.output_format = 'json'
        super(SectorCollection, self).__init__(**kwargs)

    @property
    def url(self):
        return '/stock/market/collection/sector?collectionName={}'.format(self.sector)

# These are the sectors we're interested in trading.
# They can be individually commented out if you wish to avoid one sector or another.
sectors = [
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

def initialize(context):
    # Rebalance monthly on the first day of the month at market open.
    schedule_function(rebalance,
                      date_rule=date_rules.month_start(),
                      time_rule=time_rules.market_open())

def before_trading_start(context, data):
    # Update our target securities before market open in case it's time to rebalance when the market does open.

    # We want to buy the top 50 stocks - by market cap - in the 2 sectors we think are best.
    num_stocks = 50
    num_sectors_to_buy = 2

    sector_pe_ratios = {}
    sector_fundamental_dfs = {}
    for sector in sectors:
        fundamental_df = build_sector_fundamentals(sector)
        # We want to buy in the sectors with the highest average PE of their top companies.
        fundamental_df = fundamental_df.sort_values(by=['market_cap'], ascending=False)
        filtered_fundamental_df = get_filtered_fundamental_df(fundamental_df)
        sector_fundamental_dfs[sector] = filtered_fundamental_df
        sector_pe_ratios[sector] = filtered_fundamental_df['pe_ratio'][:num_stocks].mean()

    # Find the stocks for the sectors with the highest PE ratios.
    sector_pe_ratios = [(k, sector_pe_ratios[k]) for k in sorted(
            sector_pe_ratios,
            key=sector_pe_ratios.get,
            reverse=True
        )]
    context.stocks = []
    for i in range(0, num_sectors_to_buy):
        sector = sector_pe_ratios[i][0]
        # Get a list of the top stocks (by market cap) for the sector.
        sector_stocks = list(sector_fundamental_dfs[sector][:num_stocks].index.values)
        context.stocks += sector_stocks

def get_filtered_fundamental_df(fundamental_df):
    # This is where we remove stocks that don't meet our criteria.
    return fundamental_df[
        (fundamental_df.quick_ratio >= 1) & \
        (fundamental_df.pe_ratio < 15) & \
        (fundamental_df.pb_ratio < 1.5)
    ]

def rebalance(context):
    # Exit all positions we wish to drop before starting new ones.
    for stock in context.portfolio.positions:
        if stock not in context.stocks:
            order_target_percent(stock, 0)

    # Rebalance all stocks to target weights.
    for stock in context.stocks:
        # Determine how much of the portfolio should be allocated to this stock.
        weight = get_weight(context, stock)
        if weight != 0:
            try:
                order_target_percent(symbol(stock), weight)
            except:
                print('Error: Tried to purchase {} but there was an error.'.format(stock))
                pass

def build_sector_fundamentals(sector):
    stocks = get_sector(sector)
    if len(stocks) == 0:
        raise ValueError("Invalid sector name: {}".format(sector))

    # If we can't see its PE here, we're probably not interested in a stock. Omit it from batch queries.
    stocks = [s for s in stocks if s['peRatio'] is not None]

    # IEX doesn't like batch queries for more than 100 symbols at a time.
    # We need to build our fundamentals info iteratively.
    batch_idx = 0
    batch_size = 99
    fundamentals_dict = {}
    while batch_idx < len(stocks):
        symbol_batch = [s['symbol'] for s in stocks[batch_idx:batch_idx+batch_size]]
        stock_batch = Stock(symbol_batch)

        # Pull all the data we'll need from IEX.
        financials_json = stock_batch.get_financials()
        quote_json = stock_batch.get_quote()
        stats_json = stock_batch.get_key_stats()

        for symbol in symbol_batch:
            fundamentals_dict[symbol] = {}

            if len(financials_json[symbol]) < 1 or quote_json[symbol]['latestPrice'] is None:
                # No recent data was found. This can sometimes happen in case of recent markert suspensions.
                continue

            # Use only the most recent financial report for this stock.
            financials = financials_json[symbol][0]
            if financials['totalAssets'] is None or financials['currentAssets'] is None:
                # Ignore companies who reported no assets on their balance sheet.
                continue

            if stats_json[symbol]['sharesOutstanding'] == 0:
                # Company may have recently gone private, or there may be some other issue.
                continue

            if quote_json[symbol]['marketCap'] is None or quote_json[symbol]['marketCap'] == 0:
                # Ignore companies IEX cannot report market cap for.
                continue

            # Calculate PB ratio.
            book_value = financials['totalAssets'] - financials['totalLiabilities'] \
                                        if financials['totalLiabilities'] else financials['totalAssets']
            book_value_per_share = book_value / stats_json[symbol]['sharesOutstanding']
            fundamentals_dict[symbol]['pb_ratio'] = quote_json[symbol]['latestPrice'] / book_value_per_share

            # Approximate Morningstar's "quick ratio" - current liquidity minus debt - as closely as IEX data can.
            # If no debt is reported, just set it to 2, since the algorithm only cares that it's over 1.
            fundamentals_dict[symbol]['quick_ratio'] = financials['currentAssets'] / financials['currentDebt'] \
                                        if financials['currentDebt'] else 2

            # Store our information for this stock so we can filter on the data later.
            fundamentals_dict[symbol]['pe_ratio'] = quote_json[symbol]['peRatio']
            fundamentals_dict[symbol]['market_cap'] = quote_json[symbol]['marketCap']
            fundamentals_dict[symbol]['shares_outstanding'] = stats_json[symbol]['sharesOutstanding']
        batch_idx += batch_size
    fundamentals_df = pd.DataFrame.from_dict(fundamentals_dict).T
    return fundamentals_df

def get_weight(context, stock):
    # For now, this simply weights all stocks in our chosen sectors equally.
    # If you wish to improve this algorithm's performance, you might start by weighting your positions by market cap.

    if len(context.stocks) == 0:
        return 0
    else:
        weight = 1.0/len(context.stocks)
        return weight

def handle_data(context, data):
    # We're not interested in tracking price updates as they happen.
    pass