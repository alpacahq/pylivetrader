from pylivetrader.backend import alpaca
from unittest.mock import Mock, patch
from requests.exceptions import HTTPError
import pytest

from alpaca_trade_api.entity import Asset, Account, Position, Order
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
