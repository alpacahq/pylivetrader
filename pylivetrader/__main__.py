#
# Copyright 2015 Quantopian, Inc.
# Modifications Copyright 2018 Alpaca
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.


from pathlib import Path
import click

from pylivetrader.misc import configloader
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
    '--backend-config',
    type=click.Path(
        exists=True, file_okay=True, dir_okay=False,
        readable=True, resolve_path=True),
    default=None,
    help='Path to broker backend config file.')
@click.option(
    '--data-frequency',
    type=click.Choice({'daily', 'minute'}),
    default='minute',
    show_default=True,
    help='The data frequency of the live trade.')
@click.option(
    '-s', '--statefile',
    default=None,
    type=click.Path(writable=True),
    help='Path to the state file. Use <algofile>-state.pkl by default.')
@click.option(
    '-z', '--zipline',
    default=False,
    is_flag=True,
    help='Run with zipline algofile in magic translation (pre-alpha).'
         'With current translator, line # information will be lost and makes '
         'it hard to debug algorithm. We recommend manual translation.'
    )
@click.pass_context
def run(ctx,
        algofile,
        backend,
        backend_config,
        data_frequency,
        statefile,
        zipline):
    if algofile is None or algofile == '':
        ctx.fail("must specify algo file with '-f' ")

    if not (Path(algofile).exists() and Path(algofile).is_file()):
        ctx.fail("couldn't find algofile '{}'".format(algofile))

    functions = get_functions_by_path(algofile, use_translate=zipline)

    backend_options = None
    if backend_config is not None:
        backend_options = configloader.load_config(backend_config)

    algorithm = Algorithm(
        backend=backend,
        backend_options=backend_options,
        data_frequency=data_frequency,
        algoname=extract_filename(algofile),
        statefile=statefile,
        **functions,
    )

    with LiveTraderAPI(algorithm):

        algorithm.run()


@click.command()
def version():
    from ._version import VERSION
    click.echo('v{}'.format(VERSION))


def extract_filename(algofile):
    algofilename = algofile
    if '/' in algofilename:
        algofilename = algofilename.split('/')[-1]
    if '.py' in algofilename:
        algofilename = algofilename[:-3]
    return algofilename


main.add_command(run)
main.add_command(version)


if __name__ == '__main__':
    main()
