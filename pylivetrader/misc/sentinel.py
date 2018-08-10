#
# Copyright 2016 Quantopian, Inc.
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

"""
Construction of sentinel objects.

Sentinel objects are used when you only care to check for object identity.
"""
import sys
from textwrap import dedent


def sentinel(name, doc=None):
    try:
        value = sentinel._cache[name]  # memoized
    except KeyError:
        pass
    else:
        if doc == value.__doc__:
            return value

        raise ValueError(dedent(
            """\
            New sentinel value %r conflicts with an existing sentinel of the
            same name.
            Old sentinel docstring: %r
            New sentinel docstring: %r
            Resolve this conflict by changing the name of one of the sentinels.
            """,
        ) % (name, value.__doc__, doc))

    @object.__new__   # bind a single instance to the name 'Sentinel'
    class Sentinel(object):
        __doc__ = doc
        __slots__ = ('__weakref__',)
        __name__ = name

        def __new__(cls):
            raise TypeError('cannot create %r instances' % name)

        def __repr__(self):
            return 'sentinel(%r)' % name

        def __reduce__(self):
            return sentinel, (name, doc)

        def __deepcopy__(self, _memo):
            return self

        def __copy__(self):
            return self

    cls = type(Sentinel)
    try:
        # traverse up one frame to find the module where this is defined
        cls.__module__ = sys._getframe(1).f_globals['__name__']
    except (ValueError, KeyError):
        # Couldn't get the name from the calling scope, just use None.
        cls.__module__ = None

    sentinel._cache[name] = Sentinel  # cache result
    return Sentinel


sentinel._cache = {}
