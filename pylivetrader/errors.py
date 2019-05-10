#
# Copyright 2015 Quantopian, Inc.
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


class BadOrderParameters(LiveTraderError):
    """
    Raised if stop/limit prices in an order call are not reasonable.
    """
    msg = "{msg}"


class OrderDuringInitialize(LiveTraderError):
    """
    Raised if order is called during initialize()
    """
    msg = "{msg}"


class UnsupportedOrderParameters(LiveTraderError):
    """
    Raised if a set of mutually exclusive parameters are passed to an order
    call.
    """
    msg = "{msg}"


class CannotOrderDelistedAsset(LiveTraderError):
    """
    Raised if an order is attempted for an asset which looks impossible to
    trade.
    """
    msg = "{msg}"


class RegisterTradingControlPostInit(LiveTraderError):
    # Raised if a user's script register's a trading control after initialize
    # has been run.
    msg = """
You attempted to set a trading control outside of `initialize`. \
Trading controls may only be set in your initialize method.
""".strip()


class AccountControlViolation(LiveTraderError):
    """
    Raised if the account violates a constraint set by a AccountControl.
    """
    msg = """
Account violates account constraint {constraint}.
""".strip()


class TradingControlViolation(LiveTraderError):
    """
    Raised if an order would violate a constraint set by a TradingControl.
    """
    msg = """
Order for {amount} shares of {asset} at {datetime} violates trading constraint
{constraint}.
""".strip()


class ScheduleFunctionInvalidCalendar(LiveTraderError):
    """
    Raised when schedule_function is called with an invalid calendar argument.
    """
    msg = (
        "Invalid calendar '{given_calendar}' passed to schedule_function. "
        "Allowed options are {allowed_calendars}."
    )


class RegisterAccountControlPostInit(LiveTraderError):
    # Raised if a user's script register's a trading control after initialize
    # has been run.
    msg = """
You attempted to set an account control outside of `initialize`. \
Account controls may only be set in your initialize method.
""".strip()


class HistoryInInitialize(LiveTraderError):
    """
    Raised when an algorithm calls history() in initialize.
    """
    msg = "history() should only be called in handle_data()"


class OrderInBeforeTradingStart(LiveTraderError):
    """
    Raised when an algorithm calls an order method in before_trading_start.
    """
    msg = "Cannot place orders inside before_trading_start."
