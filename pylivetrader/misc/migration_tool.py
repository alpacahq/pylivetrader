"""
this is a tool to migrate Quantopian/Zipline scripts to pylivetrader
compatible code
"""
import os


HANDLE_DATA = """
def handle_data(context, data):
    pass
"""
BEFORE_TRADING_START = """
def before_trading_start(context, data):
    pass
"""


def make_sure_source_code_is_python3_compatible(algo_path: str):
    """
    pylivetrader is supported for python 3 only.
    quantopian code still supports python 2.
    we use the lib2to3 tool to migrate any python2 compatible code to python3
    :param algo_path: path to input file
    """
    return os.popen(f"python -m lib2to3 -w {algo_path}").read()


def add_pylivetrader_imports(code: str) -> str:
    """
    add all imports from the pylivetrader api
    """
    imports = """
from pylivetrader.api import *
\r\n
"""
    return imports + code


def add_pipelinelive_imports(code: str) -> str:
    """
    check if algo is using pipeline and if so add pipeline_live imports
    """
    imports = """
from pipeline_live.data.alpaca.factors import AverageDollarVolume
from pipeline_live.data.alpaca.pricing import USEquityPricing
from pipeline_live.data.polygon.fundamentals import PolygonCompany
from zipline.pipeline import Pipeline
"""
    if "pipeline" in code:
        return imports + code
    return code


def define_logger(code: str) -> str:
    """
    quantopian has a default logger called "log"
    we add a logger that prints to the console which will make sure all log
    usage will stay valid.
    """

    logger = """

from logbook import Logger, StreamHandler
import sys
StreamHandler(sys.stdout).push_application()
log = Logger(__name__)

"""
    return logger + code


def check_for_unsupported_modules(code: str) -> None:
    """
    we only support open source packages. some of quantopian's imports are
    not opened source meaning we cannot execute them inside pylivetrader.
    when that happens we fail the process of migration.
    """
    for line in code.splitlines():
        if "import" in line and "optimize" in line:
            raise Exception("Optimize is not supported in pylivetrader")


def add_missing_base_methods(code: str) -> str:
    """
    when writing a quantopian/zipline algorithm you are not obligated to
    implement all methods. so if these methods are not present we add dummy
    implementations.
    :param code:
    :return:
    """
    if "def handle_data(" not in code:
        code += HANDLE_DATA
    if "def before_trading_start(" not in code:
        code += BEFORE_TRADING_START
    return code


def remove_quantopian_imports(code: str) -> str:
    """
    we implement the algorithm api inside pylivetrader.
    the quantopian api is removed.
    :param code:
    :return:
    """
    result = []
    skip_next_line = False
    for line in code.splitlines():
        if "import" in line and "\\" in line:
            skip_next_line = True
        if skip_next_line:
            if "\\" not in line:
                skip_next_line = False
            continue
        if "import" in line and "quantopian" in line:
            continue
        result.append(line)
    return "\r\n".join(result)


def remove_commission(code: str) -> str:
    """
    commission and slippage are not relevant when you are not back testing.
    we remove it from the code.
    """
    result = []
    for line in code.splitlines():
        if "set_commission" in line or "set_slippage" in line:
            continue
        result.append(line)
    return "\r\n".join(result)


def cleanup(code: str) -> str:
    """
    this method will be used to cleanup the final result
    :param code:
    :return:
    """
    def _remove_double_spaces(code1: str) -> str:
        """
        remove double space lines
        """
        while "\n\n" in code1 or "\r\n\r\n" in code1 or "\n\r\n" in code1:
            code1 = code1.replace("\n\n", "\n")
            code1 = code1.replace("\r\n\r\n", "\r\n")
            code1 = code1.replace("\n\r\n", "\r\n")
        code1 = code1.replace("\r\n", "\n")
        return code1

    return _remove_double_spaces(code)


if __name__ == '__main__':
    algoname = "example_q.py"
    print(os.popen("python -m lib2to3 -w {}".format(algoname)).read())
    data = open("example_q.py", "r").read()
    check_for_unsupported_modules(algoname)
    data = remove_quantopian_imports(data)
    data = remove_commission(data)
    data = add_missing_base_methods(data)
    data = define_logger(data)
    data = add_pipelinelive_imports(data)
    data = add_pylivetrader_imports(data)
    data = cleanup(data)
    print(data)
