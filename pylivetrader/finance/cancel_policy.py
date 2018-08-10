
class Base:
    '''Just for API compatibility, do nothing'''

    def __init__(self, *args, **kwargs):
        pass


class EODCancel(Base):
    pass


class NeverCancel(Base):
    pass
