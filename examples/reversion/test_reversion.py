import unittest
import numpy as np
from alpaca_trade_api.entity import Position
from reversion import (
    is_expired,
    get_stop_price,
    get_cost,
    increment_day,
    add_to_tracker,
    clean_tracker,
)

class TestReversion(unittest.TestCase):

    def test_is_expired(self):
        self.assertTrue(is_expired(6))

    def test_get_stop_price(self):
        self.assertEqual(3.75,get_stop_price(10, 2.5))
        self.assertEqual(0,get_stop_price(2, 2.5))

    def test_get_cost(self):
        self.assertEqual(960,get_cost(5, 10000, 60))

    def test_increment_day(self):
        tracker = { 'AAPL': {'atr': '3', 'days': '1'}, 'FB': {'atr': '4', 'days':'2'}}
        tracker_updated = { 'AAPL': {'atr': '3', 'days': '2'}, 'FB': {'atr': '4', 'days':'3'}}
        increment_day(tracker)
        self.assertEqual(tracker, tracker_updated)

    def test_add_to_tracker_1(self):
        tracker = dict()
        tmp_tracker = {'FB': 3}
        pos_1 = Position({'symbol': 'FB'})
        positions = {pos_1}
        tracker_result = { 'FB': {'atr': '3', 'days': '0'}}
        add_to_tracker(tracker, positions, tmp_tracker)
        self.assertEqual(tracker, tracker_result)

    def test_add_to_tracker_2(self):
        tracker = { 'FB': {'atr': '4', 'days': '2'}}
        tmp_tracker = {'FB': 3}
        pos_1 = Position({'symbol': 'FB'})
        positions = {pos_1}
        tracker_result = { 'FB': {'atr': '4', 'days': '2'}}
        add_to_tracker(tracker, positions, tmp_tracker)
        self.assertEqual(tracker, tracker_result)

    def test_clean_tracker(self):
        tracker = { 'AAPL': {'atr': '3', 'days': '1'}, 'FB': {'atr': '4', 'days':'2'}}
        pos_1 = Position({'symbol': 'AAPL'})
        positions = {pos_1}
        tracker_result = {'AAPL': {'atr': '3', 'days': '1'}}
        tracker = clean_tracker(tracker, positions)
        self.assertEqual(tracker, tracker_result)
          
if __name__ == '__main__':
    unittest.main()