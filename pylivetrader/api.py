'''API redirection definitions.

All the algorithm API redirections are going to be registered by
misc.api_context#api_method method on the fly.
'''

from pylivetrader.finance import execution, commission, slippage, cancel_policy
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
]
