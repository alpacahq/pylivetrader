import examples.MACD.macd_example as algo

from pylivetrader.testing.smoke import harness


def test_algo():
    harness.run_smoke(algo)


if __name__ == '__main__':
    import sys
    from logbook import StreamHandler
    StreamHandler(sys.stdout).push_application()

    test_algo()
