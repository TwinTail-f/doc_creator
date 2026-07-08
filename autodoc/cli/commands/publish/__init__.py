"""Группа команд publish."""

import click

from autodoc.cli.commands.publish.release import publish_release
from autodoc.cli.commands.publish.profile import publish_profile
from autodoc.cli.commands.publish.passports import publish_passports
from autodoc.cli.commands.publish.all import publish_all


@click.group()
def publish() -> None:
    """Публикация документации в Confluence."""


publish.add_command(publish_release)
publish.add_command(publish_profile)
publish.add_command(publish_passports)
publish.add_command(publish_all)
