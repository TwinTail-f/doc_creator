from pathlib import Path
from autodoc.config.manager import ConfigManager


class CliCtx:
    """Контекст, разделяемый между командами Click."""

    def __init__(self, base_dir: Path, configs_dir: Path, verbose: bool) -> None:
        self.base_dir = base_dir
        self.configs_dir = configs_dir
        self.verbose = verbose
        self.config_manager = ConfigManager(configs_dir)
