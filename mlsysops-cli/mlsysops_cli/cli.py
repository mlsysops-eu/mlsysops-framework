# mlsysops_cli/cli.py
import click
from .commands.apps import apps
from .commands.infra import infra
from .commands.manage import manage
from .commands.ml import ml
from .commands.agent import agent

@click.group(help="Command-line interface for MLSysOps")
def cli():
    pass

cli.add_command(apps)
cli.add_command(infra)
cli.add_command(manage)
cli.add_command(ml)
cli.add_command(agent)

if __name__ == "__main__":
    cli()

