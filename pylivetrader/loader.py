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

import ast
import astor
from six import exec_
import os

from pylivetrader import api

from logbook import Logger

log = Logger('loader')


def get_api_functions(ns):
    api_methods = {
        'initialize',
        'handle_data',
        'before_trading_start',
        # Skip zipline's analyze API as it is not part of live trading.
        # 'analyze',
    }

    out = {}

    for m in api_methods:
        out[m] = ns.get(m, noop)

    return out


def get_algomodule_by_path(path):
    with open(path, 'r') as f:
        file = f.read()
        filename = os.path.basename(path)

        return get_algomodule(file, filename)


def get_algomodule(script, filename=None):
    if filename is None:
        filename = '<script>'

    code = compile(script, filename, 'exec')

    ns = {}
    for name in api.__all__:
        ns[name] = getattr(api, name)

    exec_(code, ns)

    return ns


def get_functions(script, filename=None):
    return get_api_functions(get_algomodule(script))


def translate(script):
    '''translate zipline script into pylivetrader script.
    '''
    tree = ast.parse(script)

    ZiplineImportVisitor().visit(tree)

    return astor.to_source(tree)


LIST_TO_REPLACE = [
    'zipline.api',
    'zipline.errors',
]


class ZiplineImportVisitor(ast.NodeVisitor):

    def visit_Import(self, node):

        for i, ch in enumerate(node.names):

            if ch.name in LIST_TO_REPLACE:
                node.names[i].name = node.names[i].name.replace(
                    'zipline.', 'pylivetrader.')

        return node

    def visit_ImportFrom(self, node):

        if node.module in LIST_TO_REPLACE:
            node.module = node.module.replace('zipline.', 'pylivetrader.')
            return node

        if node.module == 'zipline':
            for name in node.names:
                if name.name not in ['api', 'errors']:
                    log.warning(
                        'pylivetrader does not supports {}.{} module.'
                        ' Fallback to load zipline'.format(
                            node.module, name.name))
                    return node
            node.module = 'pylivetrader'

        return node


def noop(*args, **kwargs):
    pass
