from pylivetrader.misc.api_context import LiveTraderAPI
from pylivetrader.algorithm import Algorithm
from pylivetrader.loader import get_functions_by_path


def main(path, backend='alpaca'):

    functions = get_functions_by_path(path)

    algorithm = Algorithm(backend=backend, **functions)

    with LiveTraderAPI(algorithm):

        algorithm.run()


if __name__ == '__main__':
    import fire
    fire.Fire(main)
