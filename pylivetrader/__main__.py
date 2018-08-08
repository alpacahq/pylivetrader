from pathlib import Path
import click

from pylivetrader.misc.api_context import LiveTraderAPI
from pylivetrader.algorithm import Algorithm
from pylivetrader.loader import get_functions_by_path


@click.group()
def main():
    from logbook import StreamHandler
    import sys
    StreamHandler(sys.stdout).push_application()


@click.command()
@click.option(
    '-f', '--algofile',
    default=None,
    type=click.Path(
        exists=True, file_okay=True, dir_okay=False,
        readable=True, resolve_path=True),
    help='Path to the file taht contains algorithm to run.')
@click.option(
    '-b', '--backend',
    default='alpaca',
    show_default=True,
    help='Broker backend to run algorithm with.')
@click.option(
    '--data-frequency',
    type=click.Choice({'daily', 'minute'}),
    default='daily',
    show_default=True,
    help='The data frequency of the live trade.')
@click.pass_context
def run(ctx, algofile, backend, data_frequency):
    if algofile is None or algofile == '':
        ctx.fail("must specify algo file with '-f' ")

    if not (Path(algofile).exists() and Path(algofile).is_file()):
        ctx.fail("couldn't find algofile '{}'".format(algofile))

    functions = get_functions_by_path(algofile)

    algorithm = Algorithm(
        backend=backend,
        data_frequency=data_frequency,
        **functions,
    )

    with LiveTraderAPI(algorithm):

        algorithm.run()


@click.command()
def version():
    from ._version import VERSION
    click.echo('v{}'.format(VERSION))


main.add_command(run)
main.add_command(version)


if __name__ == '__main__':
    main()
