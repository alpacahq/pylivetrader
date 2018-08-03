import pytz
from copy import copy

from pylivetrader.misc.api_context import api_method, LiveTraderAPI


class APINotSupported:
    pass


class Algorithm:
    """Provides algorithm compatible with zipline.
    """

    def __init__(self):
        self._recorded_vars = {}
        # TODO: need to be modifiable.
        self._data_frequency = 'minute'
        pass

    @api_method
    def get_environment(self, field='platform'):
        raise APINotSupported

    @api_method
    def fetch_csv(self,
                  url,
                  pre_func=None,
                  post_func=None,
                  date_column='date',
                  date_format=None,
                  timezone=pytz.utc.zone,
                  symbol=None,
                  mask=True,
                  symbol_column=None,
                  special_params_checker=None,
                  **kwargs):
        raise APINotSupported

    @api_method
    def order(self, asset, amount, limit_price=None, stop_price=None, style=None):
        raise NotImplemented

    @api_method
    def add_event(self, rule=None, callback=None):
        raise NotImplemented

    @api_method
    def add_event(self, rule=None, callback=None):
        raise NotImplemented

    @api_method
    def schedule_function(self,
                          func,
                          date_rule=None,
                          time_rule=None,
                          half_days=True,
                          calendar=None):
        raise NotImplemented

    @api_method
    def record(self, *args, **kwargs):
        '''Just do nothing for compatibility.'''
        pass

    @api_method
    def set_benchmark(self, benchmark):
        '''Just do nothing for compatibility.'''
        pass

    @api_method
    def symbol(self, symbol):
        '''Lookup equity by symbol.

        Parameters:
            symbol (string): The ticker symbol for the asset.

        Returns:
            equity (Equity): The equity object lookuped by the ``symbol``.

        Raises:
            AssetNotFound: When could not resolve the ``Asset`` by ``symbol``.
        '''
        raise NotImplemented

    @api_method
    def continuous_future(self, *args, **kwargs):
        raise APINotSupported

    @api_method
    def symbols(self, symbol):
        '''Lookup equities by symbol.

        Parameters:
            symbols (iterable[str]): List of ticker symbols for the asset.

        Returns:
            equities (List[Equity]): The equity object lookuped by the ``symbol``.

        Raises:
            AssetNotFound: When could not resolve the ``Asset`` by ``symbol``.
        '''
        raise NotImplemented

    @api_method
    def sid(self, sid):
        '''Lookup equity by asset unique identifier

        Parameters:
            sid: asset unique identifier.

        Returns:
            equity (Equity): The equity object lookuped by the ``sid``.

        Raises:
            AssetNotFound: When could not resolve the ``Asset`` by ``sid``.
        '''
        raise NotImplemented

    @api_method
    def future_symbol(self, symbol):
        raise APINotSupported

    @api_method
    def order(self, asset, amount, limit_price=None, stop_price=None, style=None):
        raise NotImplemented

    @api_method
    def order_value(self, asset, value, limit_price=None, stop_price=None, style=None):
        return NotImplemented

    @property
    def recorded_vars(self):
        return copy(self._recorded_vars)

    @property
    def portfolio(self):
        raise NotImplemented

    def set_logger(self, logger):
        self.logger = logger

    def on_dt_changed(self, dt):
        raise NotImplemented

    @api_method
    def get_datetime(self, tz=None):
        dt = self.datetime
        assert dt.tzinfo == pytz.utc, "Algorithm should have a utc datetime"
        if tz is not None:
            dt = dt.astimezone(tz)
        return dt

    @api_method
    def set_slippage(self, **kwargs):
        '''Just do nothing for compatibility.'''
        pass

    @api_method
    def set_commission(self, **kwargs):
        '''Just do nothing for compatibility.'''
        pass

    @api_method
    def set_cancel_policy(self, *args):
        '''Just do nothing for compatibility.'''
        pass

    @api_method
    def set_symbol_lookup_date(self, dt):
        raise APINotSupported

    @property
    def data_frequency(self):
        return self._data_frequency

    @api_method
    def order_percent(self, asset, percent, limit_price=None, stop_price=None, style=None):
        raise NotImplemented

    @api_method
    def order_target(self, asset, target, limit_price=None, stop_price=None, style=None):
        raise NotImplemented

    @api_method
    def order_target_value(self, asset, target, limit_price=None, stop_price=None, style=None):
        raise NotImplemented

    @api_method
    def order_target_percent(self, asset, target, limit_price=None, stop_price=None, style=None):
        raise NotImplemented

    @api_method
    def batch_market_order(self, share_counts):
        raise NotImplemented

    @api_method
    def get_open_orders(self, asset=None):
        raise NotImplemented

    @api_method
    def get_order(self, order_id):
        raise NotImplemented

    @api_method
    def cancel_order(self, order_param):
        raise NotImplemented

    @api_method
    def history(self, bar_count, frequency, field, ffill=True):
        raise NotImplemented

    def get_history_window(self, bar_count, frequency, assets, field, ffill):
        raise NotImplemented

    #
    # Account Controls
    #

    @api_method
    def set_max_leverage(self, max_leverage):
        raise APINotSupported

    @api_method
    def set_max_position_size(self, asset=None, max_shares=None, max_notional=None, on_error='fail'):
        raise APINotSupported

    @api_method
    def set_max_order_size(self,
                           asset=None,
                           max_shares=None,
                           max_notional=None,
                           on_error='fail'):
        raise APINotSupported

    @api_method
    def set_max_order_count(self, max_count, on_error='fail'):
        raise APINotSupported

    @api_method
    def set_do_not_order_list(self, restricted_list, on_error='fail'):
        raise NotImplemented

    @api_method
    def set_asset_restrictions(self, restrictions, on_error='fail'):
        raise APINotSupported

    @api_method
    def set_long_only(self, on_error='fail'):
        raise APINotSupported

    @api_method
    def attach_pipeline(self, pipeline, name, chunks=None):
        raise APINotSupported

    @api_method
    def pipeline_output(self, name):
        raise APINotSupported
