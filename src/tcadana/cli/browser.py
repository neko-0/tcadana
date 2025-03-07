from pathlib import Path

import click

from ..visualization.interactive import FieldViewer2D


@click.group(name='browser')
def cli():
    """entry point for tcadana browser"""


@cli.command()
@click.option("--file", type=str, help="path to the TDR file")
def field_viewer(file):
    """
    Given a config, reduce ntuples to histograms with addition of external weight distribution
    """
    filename = str(Path(file).resolve())
    with FieldViewer2D(filename) as viewer:
        viewer.start_server()
