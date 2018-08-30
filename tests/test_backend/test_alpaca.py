from pylivetrader.backend import alpaca
from unittest.mock import Mock, patch
from requests.exceptions import HTTPError
import pytest
import pandas as pd
import numpy as np

from alpaca_trade_api.polygon.entity import Aggs, Trade


def test_skip_http_error():

    @alpaca.skip_http_error((404, ))
    def not_found():
        raise HTTPError(response=Mock(status_code=404))

    ret = not_found()
    assert ret is None

    @alpaca.skip_http_error((404, ))
    def internal_server_error():
        raise HTTPError(response=Mock(status_code=503))

    with pytest.raises(HTTPError):
        internal_server_error()


def test_get_bars():
    backend = alpaca.Backend('key-id', 'secret-key')

    with patch.object(backend._api, 'polygon') as polygon:
        polygon.historic_agg = historic_agg_data

        assets = [Mock(symbol='AAPL')]
        res = backend.get_bars(assets, 'minute')
        assert isinstance(res, pd.DataFrame)
        assert isinstance(res.columns, pd.MultiIndex)
        t0 = res.index[0].time()
        assert t0.hour == 9 and t0.minute == 31

        res = backend.get_bars(assets[0], 'minute')
        t0 = res.index[0].time()
        assert t0.hour == 9 and t0.minute == 31

        res = backend.get_bars(assets[0], 'daily')

        polygon.last_trade.return_value = last_trade_data()
        res = backend.get_spot_value(assets, 'price', None, None)
        assert res[0] == 225.18
        res = backend.get_spot_value(assets, 'last_traded', None, None)
        assert res[0].hour == 17
        res = backend.get_spot_value(assets, 'close', None, None)
        assert res[0] > 220

        res = backend.get_spot_value(assets[0], 'price', None, None)
        assert res == 225.18
        res = backend.get_spot_value(assets[0], 'last_traded', None, None)
        assert res.hour == 17
        res = backend.get_spot_value(assets[0], 'close', None, None)
        assert res > 220

        dt = backend.get_last_traded_dt(assets[0])
        assert dt.hour == 17

        polygon.historic_agg = Mock()
        polygon.historic_agg.side_effect = HTTPError(
            response=Mock(status_code=404))
        res = backend.get_bars(assets, 'minute')
        assert res.empty

        polygon.last_trade = Mock()
        polygon.last_trade.side_effect = HTTPError(
            response=(Mock(status_code=404)))
        res = backend.get_spot_value(assets, 'price', None, None)
        assert np.isnan(res[0])
        res = backend.get_spot_value(assets, 'last_traded', None, None)
        assert len(res) == 1
        res = backend.get_spot_value(assets, 'close', None, None)
        assert np.isnan(res[0])


def last_trade_data():
    return Trade({'price': 225.18, 'size': 20,
                  'exchange': 4, 'timestamp': 1535662827458})


def historic_agg_data(size, *args, **kwargs):
    if size == 'day':
        return Aggs({'symbol': 'AAPL',
                     'aggType': 'daily',
                     'map': {'o': 'open',
                             'c': 'close',
                             'h': 'high',
                             'l': 'low',
                             'v': 'volume',
                             'd': 'day'},
                     'ticks': [{'o': 220.25,
                                'c': 222.98,
                                'h': 223.49,
                                'l': 219.41,
                                'v': 23751643,
                                'd': '2018-8-29'},
                               {'o': 219.01,
                                'c': 219.71,
                                'h': 220.54,
                                'l': 218.92,
                                'v': 19905543,
                                'd': '2018-8-28'},
                               {'o': 217.15,
                                'c': 217.99,
                                'h': 218.74,
                                'l': 216.33,
                                'v': 17763411,
                                'd': '2018-8-27'}]})
    return Aggs({'symbol': 'AAPL',
                 'aggType': 'min',
                 'map': {'o': 'open',
                         'c': 'close',
                         'h': 'high',
                         'l': 'low',
                         'v': 'volume',
                         'd': 'timestamp'},
                 'ticks': [{'o': 223.33,
                            'c': 223.46,
                            'h': 223.46,
                            'l': 223.33,
                            'v': 2795,
                            'd': 1535635200000},
                           {'o': 223.39,
                            'c': 223.35,
                            'h': 223.39,
                            'l': 223.35,
                            'v': 7323,
                            'd': 1535635260000},
                           {'o': 223.35,
                            'c': 223.4,
                            'h': 223.42,
                            'l': 223.35,
                            'v': 1724,
                            'd': 1535635320000},
                           {'o': 223.36,
                            'c': 223.43,
                            'h': 223.43,
                            'l': 223.36,
                            'v': 1404,
                            'd': 1535635380000},
                           {'o': 223.4,
                            'c': 223.36,
                            'h': 223.4,
                            'l': 223.36,
                            'v': 2630,
                            'd': 1535635440000},
                           {'o': 223.35,
                            'c': 223.35,
                            'h': 223.35,
                            'l': 223.31,
                            'v': 1678,
                            'd': 1535635500000},
                           {'o': 223.35,
                            'c': 223.35,
                            'h': 223.36,
                            'l': 223.35,
                            'v': 4153,
                            'd': 1535635560000},
                           {'o': 223.36,
                            'c': 223.37,
                            'h': 223.37,
                            'l': 223.36,
                            'v': 1393,
                            'd': 1535635620000},
                           {'o': 223.33,
                            'c': 223.38,
                            'h': 223.38,
                            'l': 223.23,
                            'v': 6022,
                            'd': 1535635680000},
                           {'o': 223.27,
                            'c': 223.26,
                            'h': 223.27,
                            'l': 223.26,
                            'v': 271,
                            'd': 1535635740000},
                           {'o': 223.25,
                            'c': 223.5999,
                            'h': 223.86,
                            'l': 223.25,
                            'v': 1001626,
                            'd': 1535635800000},
                           {'o': 223.6,
                            'c': 224.18,
                            'h': 224.19,
                            'l': 223.59,
                            'v': 362322,
                            'd': 1535635860000},
                           {'o': 224.18,
                            'c': 224.5,
                            'h': 224.53,
                            'l': 224.1799,
                            'v': 318951,
                            'd': 1535635920000},
                           {'o': 224.49,
                            'c': 224.18,
                            'h': 224.49,
                            'l': 224.07,
                            'v': 239954,
                            'd': 1535635980000},
                           {'o': 224.21,
                            'c': 224.1593,
                            'h': 224.25,
                            'l': 224.01,
                            'v': 248875,
                            'd': 1535636040000},
                           {'o': 224.16,
                            'c': 224.478,
                            'h': 224.49,
                            'l': 224.13,
                            'v': 199907,
                            'd': 1535636100000},
                           {'o': 224.47,
                            'c': 223.8065,
                            'h': 224.57,
                            'l': 223.8,
                            'v': 298215,
                            'd': 1535636160000},
                           {'o': 223.81,
                            'c': 223.61,
                            'h': 223.83,
                            'l': 223.55,
                            'v': 208515,
                            'd': 1535636220000},
                           {'o': 223.63,
                            'c': 223.4484,
                            'h': 223.82,
                            'l': 223.3208,
                            'v': 217942,
                            'd': 1535636280000},
                           {'o': 223.42,
                            'c': 223.0002,
                            'h': 223.44,
                            'l': 222.91,
                            'v': 301328,
                            'd': 1535636340000}]})
