"""Группа команд publish."""

import click

from autodoc.cli.commands.publish.all import publish_all
from autodoc.cli.commands.publish.kit_latest import publish_kit_latest
from autodoc.cli.commands.publish.kit_pinned import publish_kit_pinned
from autodoc.cli.commands.publish.passports import publish_passports
from autodoc.cli.commands.publish.profile import publish_profile
from autodoc.cli.commands.publish.release import publish_release


@click.group()
def publish() -> None:
    """Публикация документации в Confluence."""


publish.add_command(publish_release)
publish.add_command(publish_profile)
publish.add_command(publish_passports)
publish.add_command(publish_kit_pinned)
publish.add_command(publish_kit_latest)
publish.add_command(publish_all)
