#
# Copyright 2016 Quantopian, Inc.
# Modifications Copyright 2018 Alpaca
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
import pandas
import pandas as pd

from contextlib import contextmanager
from collections import Iterable

from pylivetrader.assets import Asset
from pylivetrader.misc.parallel_utils import parallelize


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

    def __init__(self, data_portal, data_frequency):

        self.data_portal = data_portal
        self.data_frequency = data_frequency
        self._daily_mode = data_frequency == 'daily'

        # Need to handle in before / after market hour
        self._adjust_minutes = False

        # datetime will be updated on on_dt_changed
        self.datetime = None

    def current(self, assets, fields):
        multiple_assets = _is_iterable(assets)
        multiple_fields = _is_iterable(fields)

        asset_list = assets if _is_iterable(assets) else [assets]
        field_list = fields if _is_iterable(fields) else [fields]

        fetch_args = []
        for asset in asset_list:
            for field in field_list:
                fetch_args.append((asset, field))

        if not self._adjust_minutes:
            def fetch(asset, field):
                return self.data_portal.get_spot_value(
                    asset,
                    field,
                    self._get_current_minute(),
                    self.data_frequency
                )
        else:
            def fetch(asset, field):
                return self.data_portal.get_adjusted_value(
                    asset,
                    field,
                    self._get_current_minute(),
                    None,  # this is used to be self.simulation_dt_func(). but
                           # it is a zipline residue, and it's not used
                           # anyways. so, just use empty arg
                    self.data_frequency
                )

        results = parallelize(fetch)(fetch_args)

        if not multiple_assets and not multiple_fields:
            # Return scalar value
            return results[(assets, fields)]
        elif multiple_assets and multiple_fields:
            # Return DataFrame indexed on field
            field_results = {field: {} for field in fields}
            for args, result in results.items():
                (asset, field) = args
                field_results[field][asset] = result
            data = {}
            for field in fields:
                series = pd.Series(
                    data=field_results[field], index=assets, name=field
                )
                data[field] = series
            return pd.DataFrame(data)
        elif multiple_assets:
            # Multiple assets, single field
            # Return Series indexed on assets
            asset_results = {}
            for args, result in results.items():
                (asset, field) = args
                asset_results[asset] = result
            return pd.Series(
                data=asset_results, index=assets, name=fields
            )
        else:
            # Single asset, multiple fields
            # Return Series indexed on fields
            field_results = {}
            for args, result in results.items():
                (asset, field) = args
                field_results[field] = result
            return pd.Series(
                data=field_results, index=fields, name=assets.symbol
            )

    def history(self, assets, fields, bar_count, frequency):
        """
        Returns a trailing window of length ``bar_count`` with data for
        the given assets, fields, and frequency, adjusted for splits, dividends,
        and mergers as of the current simulation time.
        The semantics for missing data are identical to the ones described in
        the notes for :meth:`current`.
        Parameters
        ----------
        assets: zipline.assets.Asset or iterable of zipline.assets.Asset
            The asset(s) for which data is requested.
        fields: string or iterable of string.
            Requested data field(s). Valid field names are: "price",
            "last_traded", "open", "high", "low", "close", and "volume".
        bar_count: int
            Number of data observations requested.
        frequency: str
            String indicating whether to load daily or minutely data
            observations. Pass '1m' for minutely data, '1d' for daily data.
        Returns
        -------
        history : pd.Series or pd.DataFrame or pd.Panel
            See notes below.
        Notes
        -----
        The return type of this function depends on the types of ``assets`` and
        ``fields``:
        - If a single asset and a single field are requested, the returned
          value is a :class:`pd.Series` of length ``bar_count`` whose index is
          :class:`pd.DatetimeIndex`.
        - If a single asset and multiple fields are requested, the returned
          value is a :class:`pd.DataFrame` with shape
          ``(bar_count, len(fields))``. The frame's index will be a
          :class:`pd.DatetimeIndex`, and its columns will be ``fields``.
        - If multiple assets and a single field are requested, the returned
          value is a :class:`pd.DataFrame` with shape
          ``(bar_count, len(assets))``. The frame's index will be a
          :class:`pd.DatetimeIndex`, and its columns will be ``assets``.
        - If multiple assets and multiple fields are requested, the returned
          value is a :class:`pd.DataFrame` with a pd.MultiIndex containing pairs of
           :class:`pd.DatetimeIndex`, and ``assets``, while the columns while contain the field(s).
           It has shape``(bar_count * len(assets), len(fields))``. The names of the pd.MultiIndex are
            - ``date`` if frequency == '1d'`` or ``date_time`` if frequency == '1m``, and
            - ``asset``
        If the current simulation time is not a valid market time, we use the last market close instead.
        """

        single_field = isinstance(fields, str)

        single_asset = isinstance(assets, Asset)

        if single_asset:
            asset_list = [assets]
        else:
            asset_list = assets

        if single_field:  # for one or more assets:
            df = self.data_portal.get_history_window(
                asset_list,
                self._get_current_minute(),
                bar_count,
                frequency,
                fields,
                self.data_frequency,
            )

            if self._adjust_minutes:
                adjs = self.data_portal.get_adjustments(
                    asset_list,
                    fields,
                    self._get_current_minute(),
                    self.simulation_dt_func()
                )

                df = df * adjs

            if single_asset:
                # single asset, single field: return pd.Series with pd.DateTimeIndex
                return df.loc[:, assets]
            else:
                # multiple assets, single field: return DataFrame with pd.DateTimeIndex
                # and assets in columns.
                return df
        else:  # multiple fields
            # if single_asset:
            # todo: optimize by querying multiple fields
            # Make multiple history calls, one per field, then combine results

            df_dict = {
                field: self.data_portal.get_history_window(asset_list,
                                                           self._get_current_minute(),
                                                           bar_count,
                                                           frequency,
                                                           field,
                                                           self.data_frequency,
                                                           ).loc[:, asset_list]
                for field in fields
            }

            if self._adjust_minutes:
                adjs = {
                    field: self.data_portal.get_adjustments(
                        assets,
                        field,
                        self._get_current_minute(),
                        self.simulation_dt_func()
                    )[0] for field in fields
                }

                df_dict = {field: df * adjs[field]
                           for field, df in df_dict.items()}

            dt_label = 'date' if frequency == '1d' else 'date_time'
            df = (pd.concat(df_dict,
                            keys=df_dict.keys(),
                            names=['fields', dt_label])
                  .stack(dropna=False)  # ensure we return all fields/assets/dates despite missing values
                  .unstack(level='fields'))
            df.index.set_names([dt_label, 'asset'])
            return df.sort_index()

    def can_trade(self, assets):
        """
        For the given asset or iterable of assets, returns true if all of the
        following are true:
        1) the asset is alive for the session of the current simulation time
          (if current simulation time is not a market minute, we use the next
          session)
        2) (if we are in minute mode) the asset's exchange is open at the
          current simulation time or at the simulation calendar's next market
          minute
        3) there is a known last price for the asset.

        Notes
        -----
        The second condition above warrants some further explanation.
        - If the asset's exchange calendar is identical to the simulation
        calendar, then this condition always returns True.
        - If there are market minutes in the simulation calendar outside of
        this asset's exchange's trading hours (for example, if the simulation
        is running on the CME calendar but the asset is MSFT, which trades on
        the NYSE), during those minutes, this condition will return false
        (for example, 3:15 am Eastern on a weekday, during which the CME is
        open but the NYSE is closed).

        Parameters
        ----------
        assets: Asset or iterable of assets

        Returns
        -------
        can_trade : bool or pd.Series[bool] indexed by asset.
        """
        dt = self.datetime

        if self._adjust_minutes:
            adjusted_dt = self._get_current_minute()
        else:
            adjusted_dt = dt

        data_portal = self.data_portal

        if isinstance(assets, Asset):
            return self._can_trade_for_asset(
                assets, dt, adjusted_dt, data_portal
            )
        else:
            def fetch(asset):
                return self._can_trade_for_asset(
                    asset, dt, adjusted_dt, data_portal
                )
            tradeable = parallelize(fetch)(assets)
            return pd.Series(data=tradeable, index=assets, dtype=bool)


    @property
    def calendar(self):
        return self.data_portal.trading_calendar

    def _can_trade_for_asset(self, asset, dt, adjusted_dt, data_portal):
        # if self._is_restricted(asset, adjusted_dt):
        #     return False

        if not self.data_portal.backend._api.get_asset(asset.symbol).tradable:
            return False

        # this sometimes fail even though the asset is trade-able. I cancelled
        # this check, and added the one above it

        # session_label = self.calendar.minute_to_session_label(dt)
        # if not asset.is_alive_for_session(session_label):
        #     # asset isn't alive
        #     return False

        # this condition is being commented out because of the asset VXX
        # as it turns out, there are 2 VXX assets in the Alpaca asset list.
        # one is tradable, one is not. the auto_close_date is set (first for
        # the tradable one then for the not tradable one, casuing this to fail
        # it's set in alpaca.backend.get_equities() (asset.end_date)
        # if asset.auto_close_date and session_label >= asset.auto_close_date:
        #     return False

        if not self._daily_mode:
            # Find the next market minute for this calendar, and check if this
            # asset's exchange is open at that minute.
            if self.calendar.is_open_on_minute(dt):
                dt_to_use_for_exchange_check = dt
            else:
                dt_to_use_for_exchange_check = \
                    self.calendar.next_open(dt)

            if not asset.is_exchange_open(dt_to_use_for_exchange_check):
                return False

        # spot value doesn't always exist even though the asset is trade-able
        # you could get previous prices by doing
        # data_portal.get_history_window([Equity("AAPL", "NYSE")],
        #                                adjusted_dt, 120, 'minute',
        #                                'price', '1m')
        # but it won't always contain the lasy minute.
        # I will not fail the "can_trade" method for that, and will allow the
        # user the option to try trading even though, spot price doesn't exist

        # # is there a last price?
        # return not np.isnan(
        #     data_portal.get_spot_value(
        #         asset, "price", adjusted_dt, self.data_frequency
        #     )
        # )

        return True

    def is_stale(self, assets):
        """
        For the given asset or iterable of assets, returns true if the asset
        is alive and there is no trade data for the current simulation time.

        If the asset has never traded, returns False.

        If the current simulation time is not a valid market time, we use the
        current time to check if the asset is alive, but we use the last
        market minute/day for the trade data check.

        Parameters
        ----------
        assets: Asset or iterable of assets

        Returns
        -------
        boolean or Series of booleans, indexed by asset.
        """
        dt = self.datetime
        if self._adjust_minutes:
            adjusted_dt = self._get_current_minute()
        else:
            adjusted_dt = dt

        data_portal = self.data_portal

        if isinstance(assets, Asset):
            return self._is_stale_for_asset(
                assets, dt, adjusted_dt, data_portal
            )
        else:
            return pd.Series(data={
                asset: self._is_stale_for_asset(
                    asset, dt, adjusted_dt, data_portal
                )
                for asset in assets
            })

    def _is_stale_for_asset(self, asset, dt, adjusted_dt, data_portal):
        session_label = dt.normalize()

        if not asset.is_alive_for_session(session_label):
            return False

        current_volume = data_portal.get_spot_value(
            asset, "volume",  adjusted_dt, self.data_frequency
        )

        if current_volume > 0:
            # found a current value, so we know this asset is not stale.
            return False
        else:
            # we need to distinguish between if this asset has ever traded
            # (stale = True) or has never traded (stale = False)
            last_traded_dt = \
                data_portal.get_spot_value(asset, "last_traded", adjusted_dt,
                                           self.data_frequency)

            return not (last_traded_dt is pd.NaT)

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
