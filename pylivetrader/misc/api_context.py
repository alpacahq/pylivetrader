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
                '{} method must be callled during live trading'.format(
                    f.__name__))
        return getattr(algorithm, f.__name__)(*args, **kwargs)

    # register api redirection
    setattr(pylivetrader.api, f.__name__, wrapped)
    pylivetrader.api.__all__.append(f.__name__)
    f.is_api_method = True

    return f
