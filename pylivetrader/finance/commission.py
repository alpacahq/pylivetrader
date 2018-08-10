
class Base:
    '''Just for API compatibility, do nothing'''

    def __init__(self, *args, **kwargs):
        pass


class PerShare(Base):
    pass


class PerTrade(Base):
    pass


class PerDollar(Base):
    pass
