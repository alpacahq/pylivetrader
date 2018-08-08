import ast
import astor
from six import exec_

from pylivetrader import api

from logbook import Logger

log = Logger('loader')


def get_functions_by_path(path):

    with open(path, 'r') as f:
        file = f.read()

        filename = path
        if '/' in filename:
            filename = path.split('/')[-1]

        return get_functions(file, filename)


def get_functions(script, filename=None):

    if filename is None:
        filename = '<script>'

    # With translate, file will be rewrited and lost line # information
    # script = translate(script)

    code = compile(script, filename, 'exec')

    ns = {}
    for name in api.__all__:
        ns[name] = getattr(api, name)

    exec_(code, ns)

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
