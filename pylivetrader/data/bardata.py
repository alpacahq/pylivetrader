import pandas as pd

from contextlib import contextmanager
from collections import Iterable

from pylivetrader.assets import Asset


@contextmanager
def handle_non_market_minutes(bar_data):
    try:
        bar_data._adjust_minutes = True
        yield
    finally:
        bar_data._adjust_minutes = False


def _is_iterable(d):
    return isinstance(d, Iterable) and not isinstance(d, str)


class BarData:

    def __init__(self, data_portal, data_frequency, universe_func):

        self.data_portal = data_portal
        self.data_frequency = data_frequency
        self._daily_mode = data_frequency == 'daily'
        self.universe_func = universe_func

        # Need to handle in before / after market hour
        self._adjust_minutes = False

        # datetime will be updated on on_dt_changed
        self.datetime = None

    def current(self, assets, fields):
        multiple_assets = _is_iterable(assets)
        multiple_fields = _is_iterable(fields)

        if not multiple_assets:
            asset = assets

            if not multiple_fields:
                field = fields

                # return scalar value
                if not self._adjust_minutes:
                    return self.data_portal.get_spot_value(
                        asset,
                        field,
                        self._get_current_minute(),
                        self.data_frequency
                    )
                else:
                    return self.data_portal.get_adjusted_value(
                        asset,
                        field,
                        self._get_current_minute(),
                        self.simulation_dt_func(),
                        self.data_frequency
                    )
            else:
                # assume fields is iterable
                # return a Series indexed by field
                if not self._adjust_minutes:
                    return pd.Series(data={
                        field: self.data_portal.get_spot_value(
                                    asset,
                                    field,
                                    self._get_current_minute(),
                                    self.data_frequency
                               )
                        for field in fields
                    }, index=fields, name=assets.symbol)
                else:
                    return pd.Series(data={
                        field: self.data_portal.get_adjusted_value(
                                    asset,
                                    field,
                                    self._get_current_minute(),
                                    self.datetime,
                                    self.data_frequency
                               )
                        for field in fields
                    }, index=fields, name=assets.symbol)
        else:
            if not multiple_fields:
                field = fields

                # assume assets is iterable
                # return a Series indexed by asset
                if not self._adjust_minutes:
                    return pd.Series(data={
                        asset: self.data_portal.get_spot_value(
                                    asset,
                                    field,
                                    self._get_current_minute(),
                                    self.data_frequency
                               )
                        for asset in assets
                        }, index=assets, name=fields)
                else:
                    return pd.Series(data={
                        asset: self.data_portal.get_adjusted_value(
                                    asset,
                                    field,
                                    self._get_current_minute(),
                                    self.datetime,
                                    self.data_frequency
                               )
                        for asset in assets
                        }, index=assets, name=fields)

            else:
                # both assets and fields are iterable
                data = {}

                if not self._adjust_minutes:
                    for field in fields:
                        series = pd.Series(data={
                            asset: self.data_portal.get_spot_value(
                                        asset,
                                        field,
                                        self._get_current_minute(),
                                        self.data_frequency
                                   )
                            for asset in assets
                            }, index=assets, name=field)
                        data[field] = series
                else:
                    for field in fields:
                        series = pd.Series(data={
                            asset: self.data_portal.get_adjusted_value(
                                        asset,
                                        field,
                                        self._get_current_minute(),
                                        self.datetime,
                                        self.data_frequency
                                   )
                            for asset in assets
                            }, index=assets, name=field)
                        data[field] = series

                return pd.DataFrame(data)


    def history(self, assets, fields, bar_count, frequency):

        if type(fields) == str:
            single_asset = isinstance(assets, Asset)

            if single_asset:
                asset_list = [assets]
            else:
                asset_list = assets

            df = self.data_portal.get_history_window(
                asset_list,
                self._get_current_minute(),
                bar_count,
                frequency,
                fields,
                self.data_frequency,
            )

            if single_asset:
                return df[assets]
            else:
                return df
        else:
            single_asset = isinstance(assets, Asset)

            if single_asset:

                df_dict = {
                    field: self.data_portal.get_history_window(
                        [assets],
                        self._get_current_minute(),
                        bar_count,
                        frequency,
                        field,
                        self.data_frequency,
                    )[assets] for field in fields
                }

                return pd.DataFrame(df_dict)

            else:

                df_dict = {
                    field: self.data_portal.get_history_window(
                        assets,
                        self._get_current_minute(),
                        bar_count,
                        frequency,
                        field,
                        self.data_frequency,
                    ) for field in fields
                }

                return pd.Panel(df_dict)

    def can_trade(self, assets):
        raise NotImplementedError

    def current_dt(self):
        return self.datetime

    def _get_current_minute(self):
        """
        Internal utility method to get the current simulation time.

        Possible answers are:
        - whatever the algorithm's get_datetime() method returns (this is what
            `self.simulation_dt_func()` points to)
        - sometimes we're knowingly not in a market minute, like if we're in
            before_trading_start.  In that case, `self._adjust_minutes` is
            True, and we get the previous market minute.
        - if we're in daily mode, get the session label for this minute.
        """

        dt = self.datetime

        if self._adjust_minutes:
            dt = \
                self.data_portal.trading_calendar.previous_minute(dt)

        if self._daily_mode:
            # if we're in daily mode, take the given dt (which is the last
            # minute of the session) and get the session label for it.
            dt = self.data_portal.trading_calendar.minute_to_session_label(dt)

        return dt
