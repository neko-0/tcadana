import click
from ..version import __version__
from . import browser


@click.group(context_settings=dict(help_option_names=['-h', '--help']))
@click.version_option(version=__version__)
def tcadana():
    pass


tcadana.add_command(browser.cli)
