from IPython.terminal.embed import InteractiveShellEmbed
from pylivetrader.data.bardata import BarData
import pandas as pd


def start_shell(algorithm, algomodule):
    algomodule['context'] = algorithm
    algomodule['data'] = BarData(
        algorithm.data_portal,
        algorithm.data_frequency)
    algorithm.on_dt_changed(pd.Timestamp.utcnow().floor('1min'))
    algomodule['data'].datetime = algorithm.datetime
    algomodule['initialize'](algorithm)
    InteractiveShellEmbed()('*** pylivetrader shell ***', local_ns=algomodule)
