from pylivetrader.backend import alpaca
from unittest.mock import Mock, patch
from requests.exceptions import HTTPError
import pytest
import pandas as pd
import numpy as np

from alpaca_trade_api.entity import Asset, Account, Position, Order
from alpaca_trade_api.polygon.entity import Aggs, Trade
from alpaca_trade_api.rest import APIError

from pylivetrader.misc.api_context import LiveTraderAPI
from pylivetrader.finance.execution import (
    MarketOrder,
    LimitOrder,
    StopOrder,
    StopLimitOrder,
)
from pylivetrader.finance.order import (
    ORDER_STATUS as ZP_ORDER_STATUS
)


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


def test_orders():
    backend = alpaca.Backend('key-id', 'secret-key')
    with patch.object(backend, '_api') as _api:
        _api.list_assets.return_value = [
            Asset({'id': 'bcfdb21a-760c-44a6-a3af-6264851b5c1b',
                   'asset_class': 'us_equity',
                   'exchange': 'NYSE',
                   'symbol': 'X',
                   'status': 'inactive',
                   'tradable': True}),
            Asset({'id': '93f58d0b-6c53-432d-b8ce-2bad264dbd94',
                   'asset_class': 'us_equity',
                   'exchange': 'NASDAQ',
                   'symbol': 'AAPL',
                   'status': 'active',
                   'tradable': True}),
            Asset({'id': '8688f60a-04c9-4740-8468-c0b994499f41',
                   'asset_class': 'us_equity',
                   'exchange': 'NYSE',
                   'symbol': 'BAC',
                   'status': 'active',
                   'tradable': True}),
        ]

        res = backend._symbols2assets(['AAPL'])
        assert len(res) == 1

        _api.get_account.return_value = Account({
            'account_blocked': False,
            'buying_power': '43.38',
            'cash': '35036.18',
            'cash_withdrawable': '43.38',
            'created_at': '2018-08-27T18:33:56.812574Z',
            'currency': 'USD',
            'id': 'da66e4e6-db7e-4c2e-83ae-2e0cce995cf2',
            'pattern_day_trader': False,
            'portfolio_value': '49723.85',
            'status': 'ACTIVE',
            'trading_blocked': False,
            'transfers_blocked': False})
        res = backend.account
        assert res.buying_power < 100

        _api.list_positions.return_value = [
            Position({
                'asset_class': 'us_equity',
                'asset_id': '93f58d0b-6c53-432d-b8ce-2bad264dbd94',
                'avg_entry_price': '198',
                'change_today': '0',
                'cost_basis': '200',
                'current_price': '200',
                'exchange': 'NASDAQ',
                'lastday_price': '200',
                'market_value': '200',
                'qty': '1',
                'side': 'long',
                'symbol': 'AAPL',
                'unrealized_intraday_pl': '0',
                'unrealized_intraday_plpc': '0',
                'unrealized_pl': '2',
                'unrealized_plpc': '0.01111'}),
        ]

        algo = Mock()
        algo._backend = backend
        algo.symbol = lambda x: backend._symbols2assets([x])[0]
        with LiveTraderAPI(algo):
            res = backend.portfolio
            assert res.cash > 30e3
            assert len(res.positions) == 1

            _api.list_orders.return_value = [
                Order({
                    'asset_class': 'us_equity',
                    'asset_id': '93f58d0b-6c53-432d-b8ce-2bad264dbd94',
                    'canceled_at': None,
                    'client_order_id': 'my_id_open',
                    'created_at': '2018-08-29T13:31:02.779465Z',
                    'expired_at': None,
                    'failed_at': None,
                    'filled_at': None,
                    'filled_avg_price': None,
                    'filled_qty': '0',
                    'id': '6abca255-bc5a-4688-a547-4bfd2c33a979',
                    'limit_price': '1.3',
                    'order_type': 'limit',
                    'qty': '3846',
                    'side': 'buy',
                    'status': 'new',
                    'stop_price': None,
                    'submitted_at': '2018-08-29T13:31:02.779394Z',
                    'symbol': 'AAPL',
                    'time_in_force': 'day',
                    'type': 'limit',
                    'updated_at': '2018-08-30T19:59:00.737786Z'}),
                Order({
                    'asset_class': 'us_equity',
                    'asset_id': '93f58d0b-6c53-432d-b8ce-2bad264dbd94',
                    'canceled_at': None,
                    'client_order_id': 'my_id_failed',
                    'created_at': '2018-08-29T13:31:02.779465Z',
                    'expired_at': None,
                    'failed_at': '2018-08-29T13:31:02.779465Z',
                    'filled_at': None,
                    'filled_avg_price': None,
                    'filled_qty': '0',
                    'id': '6abca255-bc5a-4688-a547-4bfd2c33a979',
                    'limit_price': '1.3',
                    'order_type': 'limit',
                    'qty': '3846',
                    'side': 'buy',
                    'status': 'new',
                    'stop_price': None,
                    'submitted_at': '2018-08-29T13:31:02.779394Z',
                    'symbol': 'AAPL',
                    'time_in_force': 'day',
                    'type': 'limit',
                    'updated_at': '2018-08-30T19:59:00.737786Z'}),
                Order({
                    'asset_class': 'us_equity',
                    'asset_id': '93f58d0b-6c53-432d-b8ce-2bad264dbd94',
                    'canceled_at': None,
                    'client_order_id': 'my_id_filled',
                    'created_at': '2018-08-29T13:31:02.779465Z',
                    'expired_at': None,
                    'failed_at': None,
                    'filled_at': '2018-08-29T13:31:02.779465Z',
                    'filled_avg_price': '200',
                    'filled_qty': '0',
                    'id': '6abca255-bc5a-4688-a547-4bfd2c33a979',
                    'limit_price': '1.3',
                    'order_type': 'limit',
                    'qty': '3846',
                    'side': 'buy',
                    'status': 'new',
                    'stop_price': None,
                    'submitted_at': '2018-08-29T13:31:02.779394Z',
                    'symbol': 'AAPL',
                    'time_in_force': 'day',
                    'type': 'limit',
                    'updated_at': '2018-08-30T19:59:00.737786Z'}),
            ]
            res = backend.orders
            # make sure order status is set correctly
            assert res['my_id_open']._status == ZP_ORDER_STATUS.OPEN
            assert res['my_id_failed']._status == ZP_ORDER_STATUS.REJECTED
            assert res['my_id_filled']._status == ZP_ORDER_STATUS.FILLED

            _api.submit_order.return_value = Order({
                'asset_class': 'us_equity',
                'asset_id': '93f58d0b-6c53-432d-b8ce-2bad264dbd94',
                'canceled_at': None,
                'client_order_id': '439dca01703b4674a61a72713a612d24',
                'created_at': '2018-08-29T13:31:01.710698Z',
                'expired_at': None,
                'failed_at': None,
                'filled_at': None,
                'filled_avg_price': None,
                'filled_qty': '0',
                'id': '2c366657-fdbd-4554-a14d-b19df2bf430c',
                'limit_price': '2.05',
                'order_type': 'limit',
                'qty': '1',
                'side': 'buy',
                'status': 'new',
                'stop_price': None,
                'submitted_at': '2018-08-29T13:31:01.710651Z',
                'symbol': 'AAPL',
                'time_in_force': 'day',
                'type': 'limit',
                'updated_at': '2018-08-30T19:59:00.553942Z'})

            aapl = algo.symbol('AAPL')
            # this response is not correct logically, but fine for testing
            res = backend.order(aapl, 1, MarketOrder())
            assert res.limit > 1
            # different order types should go through
            backend.order(aapl, 1, LimitOrder(limit_price=100))
            backend.order(aapl, 1, StopOrder(stop_price=200))
            backend.order(
                aapl, 1, StopLimitOrder(
                    limit_price=100, stop_price=200))

            backend.cancel_order('some-id')

            # order submission fail
            _api.submit_order.side_effect = APIError({'message': 'test'})
            res = backend.order(aapl, -1, MarketOrder())
            assert res is None


def test_data():
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

        # Make sure close is used instead of trade in compatibility mode.
        res = backend.get_spot_value(assets, 'price', None, None, True)
        assert res[0] == 223.0002

        polygon.last_trade.return_value = last_trade_data()
        res = backend.get_spot_value(assets, 'price', None, None, False)
        assert res[0] == 225.18
        res = backend.get_spot_value(assets, 'last_traded', None, None, False)
        assert res[0].hour == 17
        res = backend.get_spot_value(assets, 'close', None, None, False)
        assert res[0] > 220

        res = backend.get_spot_value(assets[0], 'price', None, None, False)
        assert res == 225.18
        res = backend.get_spot_value(
            assets[0], 'last_traded', None, None, False
        )
        assert res.hour == 17
        res = backend.get_spot_value(assets[0], 'close', None, None, False)
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
        res = backend.get_spot_value(assets, 'price', None, None, False)
        assert np.isnan(res[0])
        res = backend.get_spot_value(assets, 'last_traded', None, None, False)
        assert len(res) == 1
        res = backend.get_spot_value(assets, 'close', None, None, False)
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
                         't': 'timestamp'},
                 'ticks': [{'o': 223.33,
                            'c': 223.46,
                            'h': 223.46,
                            'l': 223.33,
                            'v': 2795,
                            't': 1535635200000},
                           {'o': 223.39,
                            'c': 223.35,
                            'h': 223.39,
                            'l': 223.35,
                            'v': 7323,
                            't': 1535635260000},
                           {'o': 223.35,
                            'c': 223.4,
                            'h': 223.42,
                            'l': 223.35,
                            'v': 1724,
                            't': 1535635320000},
                           {'o': 223.36,
                            'c': 223.43,
                            'h': 223.43,
                            'l': 223.36,
                            'v': 1404,
                            't': 1535635380000},
                           {'o': 223.4,
                            'c': 223.36,
                            'h': 223.4,
                            'l': 223.36,
                            'v': 2630,
                            't': 1535635440000},
                           {'o': 223.35,
                            'c': 223.35,
                            'h': 223.35,
                            'l': 223.31,
                            'v': 1678,
                            't': 1535635500000},
                           {'o': 223.35,
                            'c': 223.35,
                            'h': 223.36,
                            'l': 223.35,
                            'v': 4153,
                            't': 1535635560000},
                           {'o': 223.36,
                            'c': 223.37,
                            'h': 223.37,
                            'l': 223.36,
                            'v': 1393,
                            't': 1535635620000},
                           {'o': 223.33,
                            'c': 223.38,
                            'h': 223.38,
                            'l': 223.23,
                            'v': 6022,
                            't': 1535635680000},
                           {'o': 223.27,
                            'c': 223.26,
                            'h': 223.27,
                            'l': 223.26,
                            'v': 271,
                            't': 1535635740000},
                           {'o': 223.25,
                            'c': 223.5999,
                            'h': 223.86,
                            'l': 223.25,
                            'v': 1001626,
                            't': 1535635800000},
                           {'o': 223.6,
                            'c': 224.18,
                            'h': 224.19,
                            'l': 223.59,
                            'v': 362322,
                            't': 1535635860000},
                           {'o': 224.18,
                            'c': 224.5,
                            'h': 224.53,
                            'l': 224.1799,
                            'v': 318951,
                            't': 1535635920000},
                           {'o': 224.49,
                            'c': 224.18,
                            'h': 224.49,
                            'l': 224.07,
                            'v': 239954,
                            't': 1535635980000},
                           {'o': 224.21,
                            'c': 224.1593,
                            'h': 224.25,
                            'l': 224.01,
                            'v': 248875,
                            't': 1535636040000},
                           {'o': 224.16,
                            'c': 224.478,
                            'h': 224.49,
                            'l': 224.13,
                            'v': 199907,
                            't': 1535636100000},
                           {'o': 224.47,
                            'c': 223.8065,
                            'h': 224.57,
                            'l': 223.8,
                            'v': 298215,
                            't': 1535636160000},
                           {'o': 223.81,
                            'c': 223.61,
                            'h': 223.83,
                            'l': 223.55,
                            'v': 208515,
                            't': 1535636220000},
                           {'o': 223.63,
                            'c': 223.4484,
                            'h': 223.82,
                            'l': 223.3208,
                            'v': 217942,
                            't': 1535636280000},
                           {'o': 223.42,
                            'c': 223.0002,
                            'h': 223.44,
                            'l': 222.91,
                            'v': 301328,
                            't': 1535636340000}]})
