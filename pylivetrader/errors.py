

class LiveTraderError(Exception):
    msg = None

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    @property
    def message(self):
        return str(self)

    def __str__(self):
        return self.msg.format(**self.kwargs)

    __repr__ = __str__


class SidsNotFound(LiveTraderError):

    @property
    def plural(self):
        return len(self.sids) > 1

    @property
    def sids(self):
        return self.kwargs['sids']

    @property
    def msg(self):
        if self.plural:
            return "No assets found for sids: {sids}."
        return "No asset found for sid: {sids[0]}."


class EquitiesNotFound(SidsNotFound):

    @property
    def msg(self):
        if self.plural:
            return "No equities found for sids: {sids}."
        return "No equity found for sid: {sids[0]}."


class SymbolNotFound(LiveTraderError):
    msg = "Symbol '{symbol}' was not found"


class NotSupported(LiveTraderError):
    msg = "Not supported in livetrader."


class APINotSupported(LiveTraderError):
    msg = "API is not supported in livetrader."
