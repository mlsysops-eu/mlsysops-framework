import click

try:
    from rich.console import Console
    from rich.table import Table
    console = Console()
    RICH = True
except Exception:
    console = None
    RICH = False

def info(msg): click.secho(msg, fg="cyan", bold=True)
def ok(msg): click.secho(msg, fg="green", bold=True)
def warn(msg): click.secho(msg, fg="yellow", bold=True)
def err(msg): click.secho(msg, fg="red", bold=True)

def rule(title, color="magenta"):
    if RICH:
        console.rule(f"[bold {color}]{title}")
    else:
        click.secho(f"{'='*10} {title} {'='*10}", fg=color)

def table_kv(rows, title="Summary"):
    if RICH:
        t = Table(title=title, show_header=True, header_style="bold magenta")
        t.add_column("Key", style="bold"); t.add_column("Value")
        for k, v in rows: t.add_row(str(k), str(v))
        console.print(t)
    else:
        click.secho(title, fg="magenta", bold=True)
        for k, v in rows: click.echo(f"- {k}: {v}")
