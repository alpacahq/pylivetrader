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

import pickle
import os

try:
    import redis
except ImportError:
    pass

VERSION_LABEL = '_stateversion_'
CHECKSUM_KEY = '__state_checksum'


class FileStore(object):
    def __init__(self, path):
        self.path = path

    def save(self, state):
        with open(self.path, 'wb') as f:
            pickle.dump(state, f)

    def load(self):
        with open(self.path, 'rb') as f:
            try:
                loaded_state = pickle.load(f)
            except (pickle.UnpicklingError, IndexError):
                raise ValueError("Corrupt state file: {}".format(self.path))

        return loaded_state

    def can_load(self):
        return os.path.exists(self.path) and os.stat(self.path).st_size


class RedisStore(object):
    REDIS_STATE_KEY = 'pylivetrader_redis_state'

    def __init__(self):
        try:
            redis
        except NameError:
            raise ValueError(
                "Redis was not installed, please install the redis module."
            )

        self.redis = redis.from_url(
            os.getenv('REDIS_URL', 'redis://localhost:6379')
        )

    def save(self, state):
        self.redis.set(self.REDIS_STATE_KEY, pickle.dumps(state))

    def load(self):
        try:
            loaded_state = pickle.loads(self.redis.get(self.REDIS_STATE_KEY))
            return loaded_state
        except pickle.UnpicklingError:
            raise ValueError("Corrupt state file in redis")

    def can_load(self):
        return self.redis.exists(self.REDIS_STATE_KEY)


class StateStore:

    def __init__(self, path=None, storage_engine=None):
        if path:
            self.storage_engine = FileStore(path)
        elif storage_engine:
            self.storage_engine = storage_engine
        else:
            raise ValueError("path or storage_engine arg is required")

    def save(self, context, checksum, exclude_list):
        state = {}
        fields_to_store = list(set(context.__dict__.keys()) -
                               set(exclude_list))

        for field in fields_to_store:
            state[field] = getattr(context, field)

        state[CHECKSUM_KEY] = checksum

        self.storage_engine.save(state)

    def load(self, context, checksum):
        if not self.storage_engine.can_load():
            return

        loaded_state = self.storage_engine.load()

        if CHECKSUM_KEY not in loaded_state or \
                loaded_state[CHECKSUM_KEY] != checksum:
            raise ValueError(
                "Checksum mismatch during state load. "
                "The given state file was not created "
                "for the algorithm in use")

        del loaded_state[CHECKSUM_KEY]

        for k, v in loaded_state.items():
            setattr(context, k, v)
