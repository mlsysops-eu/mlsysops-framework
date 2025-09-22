# mlsysops_cli/utils/alias.py
import click

class AliasedGroup(click.Group):
    """A Click group that resolves short aliases to real command names,
    without listing aliases in --help."""
    def __init__(self, *args, **kwargs):
        self.aliases = kwargs.pop("aliases", {})  # dict: alias -> real command name
        super().__init__(*args, **kwargs)

    def get_command(self, ctx, cmd_name):
        # normal commands first
        rv = super().get_command(ctx, cmd_name)
        if rv is not None:
            return rv
        # resolve alias (if any)
        target = self.aliases.get(cmd_name)
        if target:
            return super().get_command(ctx, target)
        return None
