# Just for API compatibiity, do nothing

class Base:

    def __init__(self, *args, **kwargs):
        pass


class FixedSlippage(Base):
    pass


class VolumeShareSlippage(Base):
    pass
