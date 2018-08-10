#
# Copyright 2014 Quantopian, Inc.
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


'''API redirection definitions.

All the algorithm API redirections are going to be registered by
misc.api_context#api_method method on the fly.
'''

from pylivetrader.finance import execution, commission, slippage, cancel_policy
from pylivetrader.finance.asset_restrictions import (
    Restriction,
    StaticRestrictions,
    HistoricalRestrictions,
    RESTRICTION_STATES,
)
from pylivetrader.finance.slippage import FixedSlippage, VolumeShareSlippage
from pylivetrader.finance.cancel_policy import EODCancel, NeverCancel
from pylivetrader.misc import events, math_utils
from pylivetrader.misc.events import (
    calendars,
    date_rules,
    time_rules
)


__all__ = [
    'calendars',
    'date_rules',
    'time_rules',
    'events',
    'execution',
    'commission',
    'slippage',
    'cancel_policy',
    'math_utils',
    'FixedSlippage',
    'VolumeShareSlippage',
    'EODCancel',
    'NeverCancel',
    'Restriction',
    'StaticRestrictions',
    'HistoricalRestrictions',
    'RESTRICTION_STATES',
]
