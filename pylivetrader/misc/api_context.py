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

import threading
from functools import wraps

import pylivetrader.api


context = threading.local()


def set_context(algorithm):
    setattr(context, 'algorithm', algorithm)


def get_context():
    return getattr(context, 'algorithm', None)


class LiveTraderAPI:

    def __init__(self, algorithm):
        self.algo = algorithm
        self.prev_context = None

    def __enter__(self):
        self.prev_context = get_context()
        set_context(self.algo)

    def __exit__(self, *args):
        set_context(self.prev_context)


def api_method(f):
    '''
    Redirect pylivetrader.api.* operations to the algorithm
    in the local context.
    '''

    @wraps(f)
    def wrapped(*args, **kwargs):
        # Get the instance and call the method
        algorithm = get_context()
        if algorithm is None:
            raise RuntimeError(
                '{} method must be called during live trading'.format(
                    f.__name__))
        return getattr(algorithm, f.__name__)(*args, **kwargs)

    # register api redirection
    setattr(pylivetrader.api, f.__name__, wrapped)
    pylivetrader.api.__all__.append(f.__name__)
    f.is_api_method = True

    return f


def require_not_initialized(exception):
    """
    Decorator for API methods that should only be called during or before
    TradingAlgorithm.initialize.  `exception` will be raised if the method is
    called after initialize.

    Usage
    -----
    @require_not_initialized(SomeException("Don't do that!"))
    def method(self):
        # Do stuff that should only be allowed during initialize.
    """
    def decorator(method):
        @wraps(method)
        def wrapped_method(self, *args, **kwargs):
            if self.initialized:
                raise exception
            return method(self, *args, **kwargs)
        return wrapped_method
    return decorator


def require_initialized(exception):
    """
    Decorator for API methods that should only be called after
    TradingAlgorithm.initialize.  `exception` will be raised if the method is
    called before initialize has completed.

    Usage
    -----
    @require_initialized(SomeException("Don't do that!"))
    def method(self):
        # Do stuff that should only be allowed after initialize.
    """
    def decorator(method):
        @wraps(method)
        def wrapped_method(self, *args, **kwargs):
            if not self.initialized:
                raise exception
            return method(self, *args, **kwargs)
        return wrapped_method
    return decorator


def disallowed_in_before_trading_start(exception):
    """
    Decorator for API methods that cannot be called from within
    TradingAlgorithm.before_trading_start.  `exception` will be raised if the
    method is called inside `before_trading_start`.

    Usage
    -----
    @disallowed_in_before_trading_start(SomeException("Don't do that!"))
    def method(self):
        # Do stuff that is not allowed inside before_trading_start.
    """
    def decorator(method):
        @wraps(method)
        def wrapped_method(self, *args, **kwargs):
            if self._in_before_trading_start:
                raise exception
            return method(self, *args, **kwargs)
        return wrapped_method
    return decorator


def allowed_only_in_before_trading_start(exception):
    """
    Decorator for API methods that can be called only from within
    TradingAlgorithm.before_trading_start.  `exception` will be raised if the
    method is called outside `before_trading_start`.

    Usage
    -----
    @allowed_only_in_before_trading_start(SomeException("Don't do that!"))
    def method(self):
        # Do stuff that is only allowed inside before_trading_start.
    """
    def decorator(method):
        @wraps(method)
        def wrapped_method(self, *args, **kwargs):
            if not self._in_before_trading_start:
                raise exception
            return method(self, *args, **kwargs)
        return wrapped_method
    return decorator
