import pandas as pd


try:
    from pandas._libs.tslib import normalize_date
except ImportError:
    from pandas.tslib import normalize_date
