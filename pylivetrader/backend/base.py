import abc


class BaseBackend(abc.ABC):

    @abc.abstractmethod
    def get_equities(self):
        pass

    @abc.abstractmethod
    def get_equities(self):
        pass

    @property
    @abc.abstractmethod
    def positions(self):
        pass

    @property
    @abc.abstractmethod
    def portfolio(self):
        pass

    @property
    @abc.abstractmethod
    def account(self):
        pass

    @property
    @abc.abstractmethod
    def order(self, asset, amount, style):
        pass

    @abc.abstractmethod
    def get_orders(self):
        pass

    @abc.abstractmethod
    def get_last_traded_at(self, asset):
        pass

    @abs.abstractmethod
    def get_spot_value(self, assets, field, dt, date_frequency):
        pass

    @abc.abstractmethod
    def get_bars(self, assets, data_frequency, bar_count=500):
        pass
