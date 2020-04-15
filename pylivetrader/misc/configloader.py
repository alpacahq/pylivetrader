#
# Copyright 2018 Alpaca
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

import yaml
import json


def load_config(path):
    # for YAML config files
    # to fix: YAMLLoadWarning: calling yaml.load() without Loader=...
    # is deprecated, as the default Loader is unsafe we change to
    # yaml.safe_load as described here:
    # https://github.com/yaml/pyyaml/wiki/PyYAML-yaml.load(input)-Deprecation
    if path.endswith('.yaml') or path.endswith('.yml'):
        with open(path, mode='r') as f:
            o = yaml.safe_load(f)
    elif path.endswith('.json'):
        with open(path, mode='r') as f:
            o = json.load(f)
    else:
        raise ValueError(
            "Unsupported file format need to be yaml, json, ini file.")
    return o
