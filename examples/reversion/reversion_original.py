import quantopian.algorithm as algo
import numpy as np
import talib
from quantopian.pipeline import Pipeline
from quantopian.pipeline.data.builtin import USEquityPricing
from quantopian.pipeline.factors import SimpleMovingAverage, RSI, CustomFactor, Latest, AverageDollarVolume 
from quantopian.algorithm import attach_pipeline, pipeline_output
from quantopian.pipeline.data import morningstar
import copy
import math
import datetime as dt
from datetime import datetime, timedelta, date

class atr_10days_percent(CustomFactor):  
    inputs = [USEquityPricing.high, USEquityPricing.low, USEquityPricing.close]  
    window_length = 11  
    def compute(self, today, assets, out, high, low, close):  
        range_high = np.maximum(high[1:], close[:-1]) 
        range_low = np.minimum(low[1:], close[:-1])  
        out[:] = np.mean(((range_high - range_low)/close[:-1])*100, axis=0) 
        
class atr_10days(CustomFactor):
    inputs = [USEquityPricing.high, USEquityPricing.low, USEquityPricing.close]  
    window_length = 11  
    def compute(self, today, assets, out, high, low, close):  
        range_high = np.maximum(high[1:], close[:-1])
        range_low = np.minimum(low[1:], close[:-1])
        out[:] = np.mean(range_high - range_low, axis=0)  

def initialize(context):
    set_commission(commission.PerTrade(cost=0.00))
    set_slippage(slippage.FixedSlippage(spread=0.00))
    set_long_only()
 
    schedule_function(sell, date_rules.every_day(), time_rules.market_open(hours=0, minutes=5), half_days=False)
    schedule_function(buy, date_rules.every_day(), time_rules.market_open(hours=0, minutes=59), half_days=False)
    schedule_function(cancel_open_orders, date_rules.every_day(), time_rules.market_close(minutes=1), half_days=False)
    schedule_function(my_record_vars, date_rules.every_day(), time_rules.market_close(), half_days=False)
    attach_pipeline(make_pipeline(), 'my_pipeline')
    
    context.first_time = True
    context.tracker = dict()  
    context.tmp_tracker= dict()
    
def make_pipeline():
    have_market_cap = morningstar.valuation.market_cap.latest.notnull()
    
    avg_volume = SimpleMovingAverage(inputs=[USEquityPricing.volume],window_length=50)
    filter_volume = avg_volume > 500000
    
    last_price = Latest(inputs=[USEquityPricing.close], window_length=1) 
    filter_price = last_price > 1
    
    dollar_volume = AverageDollarVolume(window_length=50)
    filter_dollar_volume = dollar_volume > 2500000
    
    sma_150 = SimpleMovingAverage(inputs=[USEquityPricing.close], window_length=150)
    filter_sma_150 = USEquityPricing.close.latest > sma_150
    
    atr_10_percent = atr_10days_percent()
    filter_atr_10 = atr_10_percent > 4
    
    rsi = RSI(inputs=[USEquityPricing.close], window_length=3)
    filter_overbought = rsi < 30
    
    atr_10 = atr_10days()
    
    stocks_to_trade = have_market_cap & filter_volume & filter_price & filter_dollar_volume & filter_sma_150 & filter_atr_10 & filter_overbought

    return Pipeline(
        columns = {
            'stocks': stocks_to_trade,
            'rsi': rsi,
            'atr': atr_10
        },
        screen = (stocks_to_trade)
    )

def before_trading_start(context, data):
    context.my_output = pipeline_output('my_pipeline')
    prepare_candidates(context, data)
    
def sell(context, data):
    context.tracker = clean_tracker(context.tracker, context.portfolio.positions)
    add_to_tracker(context.tracker, context.portfolio.positions, context.tmp_tracker)
    increment_day(context.tracker)
    for security in context.portfolio.positions:
        if data.can_trade(security): 
            age = int(context.tracker[security.symbol]['days'])
            if is_expired(age):
                order_target_percent(security, 0)
            else:
                price_share = context.portfolio.positions[security].cost_basis
                atr = float(context.tracker[security.symbol]['atr'])
                stop_loss_price = get_stop_price(price_share, atr)
                if stop_loss_price > 0:
                    order_target_percent(security, 0, style=StopOrder(stop_loss_price)) 
                profit_price = price_share * 1.03
                last_price = context.portfolio.positions[security].last_sale_price
                if last_price >= profit_price:
                    order_target_percent(security, 0)
    context.tmp_tracker = dict()

def buy(context, data):
    cash_accum = 0
    for security in context.candidates:
        if security not in context.portfolio.positions and data.can_trade(security): 
            if len(context.portfolio.positions) < 10:
                price_share = data.current(security,'close')                
                cost = get_cost(context.my_output.get_value(security, 'atr'), context.portfolio.portfolio_value, price_share)
                if cost < (context.portfolio.cash - cash_accum) and is_trade(context, data):
                    order_value(security, cost, style=LimitOrder(limit_price=price_share))
                    context.tmp_tracker[security.symbol] = context.my_output.get_value(security, 'atr')
                    cash_accum = cash_accum + cost
                    
def cancel_open_orders(context, data):
    for s in get_open_orders():  
        for o in get_open_orders(s):  
            cancel_order(o) 

def my_record_vars(context, data):
    record(cash=context.portfolio.cash)

def compute_adx(stock, data):
    period = 7  
    h = data.history(stock,'high', 2*period,'1d').dropna().values  
    l = data.history(stock,'low', 2*period,'1d').dropna().values  
    c = data.history(stock,'close', 2*period,'1d').dropna().values
    if len(h) > 0:
        ta_ADX = talib.ADX(h, l, c, period)  
        adx = ta_ADX[-1]
    else:
        log.warning("No 'highs' for " + str(stock) + ". Discarding the stock when preparing candidates")
        adx = 1000
    return adx

def prepare_candidates(context, data): 
    candidates = context.my_output.copy(deep=True)
    to_remove = []
    for index, row in candidates.iterrows():         
        adx = compute_adx(index, data)
        if(adx < 45.0):
            to_remove.append(index)        
    candidates.drop(to_remove, inplace=True)   
    context.candidates = candidates.sort_values('rsi',ascending=True).head(10).index.tolist()
              
def is_trade(context, data):
    i = 0
    for s in get_open_orders():  
        for o in get_open_orders(s):  
            if o.amount > 0:
                i += 1
    i = len(context.portfolio.positions) + i 
    return False if i > 9 else True

def handle_data(context, data):
    #just makes sense in Alpaca
    if context.first_time is True:
        if len(context.portfolio.positions) > 0:
            sys.exit("Found positions not traded by the algorithm. Shutting down...")
        if len(get_open_orders()) > 0:
            sys.exit("Found open orders not traded by the algorithm. Shutting down...")
        context.first_time = False

def get_stop_price(price, atr):
    p = price - 2.5 * atr
    return 0 if p < 0 else p

def is_expired(days):
    return True if days > 4 else False

def get_cost(atr, total_value, price_share):       
    stop_loss = get_stop_price(price_share, atr)
    dollar_risk_share = price_share - stop_loss
    cash_to_risk = total_value * 0.02
    num_shares = math.floor(cash_to_risk / dollar_risk_share)
    cost = num_shares * price_share
    max_cost = total_value * 0.1
    if cost > max_cost:
        num_shares = math.floor((total_value * 0.1) / price_share)     
    cost = num_shares * price_share
    return cost

def increment_day(tracker):
    for sec in tracker:
        curr_days = int(tracker[sec]['days']) + 1
        tracker[sec]['days'] = str(curr_days)
    return tracker

def add_to_tracker(tracker, positions, tmp_tracker):
    for security in positions:
        if not (security.symbol in tracker):
            tracker[security.symbol] = {}
            tracker[security.symbol]['days'] = str(0)
            tracker[security.symbol]['atr'] = str(tmp_tracker[security.symbol])
    return tracker

def clean_tracker(tracker, positions):
    to_remove = copy.deepcopy(tracker)
    for sec in tracker:
        found = False
        for sec_pos in positions:
            if sec_pos.symbol == sec:
                found = True
                break
        if found is False:
            to_remove.pop(sec)
    return to_remove