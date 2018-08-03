

class Asset:

    def __init__(self, sid, exchange, symbol="", asset_name="", **kwargs):
        self.sid = sid
        self.sid_hash = hash(sid)
        self.exchange = exchange
        self.symbol = symbol
        self.asset_name = asset_name

        self.start_date = None
        self.end_date = None
        self.first_traded = None
        self.auto_close_date = None
        self.exchange_full = None

    def __hash__(self):
        return self.sid_hash

    def __str__(self):
        if self.symbol:
            return '{}({} [{}])'.format(type(self).__name__, self.sid, self.symbol)
        else:
            return '{}({})'.format(type(self).__name__, self.sid)

    def __repr__(self):

        attrs = ['symbol', 'asset_name', 'exchange']

        params = [
            '{}={}'.format(a, getattr(self, a))
            for a in attrs
            if getattr(self, a) != None and getattr(self, a) != ""
        ]

        return 'Asset({}, {})'.format(self.sid, ", ".join(params))

    def to_dict(self):
        return {
            'sid': self.sid,
            'symbol': self.symbol,
            'asset_name': self.asset_name,
            'start_date': self.start_date,
            'end_date': self.end_date,
            'first_traded': self.first_traded,
            'auto_close_date': self.auto_close_date,
            'exchange': self.exchange,
            'exchange_full': self.exchange_full,
        }

    def from_dict(cls, dic):
        return cls(**dic)


class Equity(Asset):
    pass
