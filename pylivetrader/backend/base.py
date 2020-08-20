#
# Copyright https://github.com/zipline-live/zipline
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

import abc
from abc import abstractmethod

import pandas as pd


class BaseBackend(abc.ABC):

    @abstractmethod
    def get_equities(self):
        pass

    @property
    @abstractmethod
    def positions(self):
        pass

    @property
    @abstractmethod
    def portfolio(self):
        pass

    @property
    @abstractmethod
    def account(self):
        pass

    @abstractmethod
    def order(self, asset, amount, style, quantopian_compatible=True):
        pass

    @abstractmethod
    def batch_order(self, args):
        pass

    @property
    @abstractmethod
    def orders(self, quantopian_compatible=True):
        pass

    @abstractmethod
    def all_orders(
        self,
        before=None,
        status='all',
        days_back=None,
        initialize=False
    ):
        pass

    @abstractmethod
    def get_last_traded_dt(self, asset):
        pass

    @abstractmethod
    def get_spot_value(
            self,
            assets,
            field,
            dt,
            date_frequency,
            quantopian_compatible=True):
        pass

    @abstractmethod
    def get_bars(self, assets, data_frequency, bar_count=500, end_dt=None):
        pass

    @property
    def time_skew(self):
        '''
        Returns:
            skew (pd.Timedelta):
                Time skew between local clock and broker server clock
        '''
        return pd.Timedelta('0s')

    def initialize_data(self, context):
        pass
