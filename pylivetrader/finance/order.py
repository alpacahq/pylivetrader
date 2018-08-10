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

import uuid
import math
from enum import IntEnum
from pylivetrader import protocol as proto


class ORDER_STATUS(IntEnum):
    OPEN = 0
    FILLED = 1
    CANCELLED = 2
    REJECTED = 3
    HELD = 4


ORDER_FIELDS_TO_IGNORE = {'type', 'direction', '_status', 'asset'}


SELL = 1 << 0
BUY = 1 << 1
STOP = 1 << 2
LIMIT = 1 << 3


class Order:
    __slots__ = ["id", "dt", "reason", "created", "asset", "amount", "filled",
                 "commission", "_status", "stop", "limit", "stop_reached",
                 "limit_reached", "direction", "type", "broker_order_id"]

    def __init__(self,
                 dt,
                 asset,
                 amount,
                 stop=None,
                 limit=None,
                 filled=0,
                 commission=0,
                 id=None,
                 ):
        """
        @dt - datetime.datetime that the order was placed
        @asset - asset for the order.
        @amount - the number of shares to buy/sell
                  a positive sign indicates a buy
                  a negative sign indicates a sell
        @filled - how many shares of the order have been filled so far
        """

        self.id = self.make_id() if id is None else id
        self.dt = dt
        self.reason = None
        self.created = dt
        self.asset = asset
        self.amount = amount
        self.filled = filled
        self.commission = commission
        self._status = ORDER_STATUS.OPEN
        self.stop = stop
        self.limit = limit
        self.stop_reached = False
        self.limit_reached = False
        self.direction = math.copysign(1, self.amount)
        # just make it None as it should not be used in live trade.
        self.type = None
        self.broker_order_id = None

    def make_id(self):
        return uuid.uuid4().hex

    def to_dict(self):
        dct = {
            name: getattr(self, name)
            for name in self.__slots__
            if name not in ORDER_FIELDS_TO_IGNORE
        }

        if self.broker_order_id is None:
            del dct['broker_order_id']

        # Adding 'sid' for backwards compatibility with downstream consumers.
        dct['sid'] = self.asset
        dct['status'] = self.status

        return dct

    def to_api_obj(self):
        return proto.Order(initial_values=self.to_dict())

    @property
    def sid(self):
        '''For backward compatibility with zipline'''
        return self.asset

    @property
    def status(self):
        if not self.open_amount:
            return ORDER_STATUS.FILLED

        if self._status == ORDER_STATUS.HELD and self.filled:
            return ORDER_STATUS.OPEN

        return self._status

    @property
    def open(self):
        return self.status in [ORDER_STATUS.OPEN, ORDER_STATUS.HELD]

    @property
    def open_amount(self):
        return self.amount - self.filled

    def __repr__(self):
        """
        String representation for this object.
        """
        return "Order(%s)" % self.to_dict().__repr__()
