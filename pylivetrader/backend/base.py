import abc
from abc import abstractmethod


class BaseBackend(abc.ABC):

    @abstractmethod
    def get_equities(self):
        pass

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

    @property
    @abstractmethod
    def order(self, asset, amount, style):
        pass

    @property
    @abstractmethod
    def orders(self):
        pass

    @abstractmethod
    def get_last_traded_dt(self, asset):
        pass

    @abstractmethod
    def get_spot_value(self, assets, field, dt, date_frequency):
        pass

    @abstractmethod
    def get_bars(self, assets, data_frequency, bar_count=500):
        pass
