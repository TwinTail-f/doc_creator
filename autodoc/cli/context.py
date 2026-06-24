from pathlib import Path
from autodoc.config.manager import ConfigManager


class CliCtx:
    """
    Контекст, разделяемый между всеми командами Click через ``ctx.obj``.

    Хранит пути проекта и заранее созданный ``ConfigManager``, чтобы каждая
    команда не дублировала их инициализацию.

    Attributes:
        base_dir: Базовая директория проекта.
        configs_dir: Директория с конфигурационными файлами.
        verbose: Флаг подробного вывода логов.
        config_manager: Менеджер для загрузки и валидации конфигов.
    """

    def __init__(self, base_dir: Path, configs_dir: Path, verbose: bool) -> None:
        """
        Args:
            base_dir: Базовая директория проекта (``--base-dir``).
            configs_dir: Директория с конфигами (``--configs-dir``).
            verbose: Включён ли подробный вывод логов (``-v``/``--verbose``).
        """
        self.base_dir = base_dir
        self.configs_dir = configs_dir
        self.verbose = verbose
        self.config_manager = ConfigManager(configs_dir)
