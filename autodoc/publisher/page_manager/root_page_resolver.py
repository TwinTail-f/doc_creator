"""Резолвер ссылок на корневые/родительские страницы Confluence."""

from autodoc.config.schemas.confluence_config import ConfluenceConfigSchema
from autodoc.exceptions import ConfigError
from autodoc.publisher.clients.confluence_client import ConfluenceClient


class RootPageResolver:
    """
    Резолвит ссылки на корневые/родительские страницы Confluence.

    Источник значения выбирается по двум правилам: между CLI и конфигом —
    CLI побеждает целиком парой (имя+ID), если задано хоть одно из двух;
    внутри одного источника — название страницы приоритетнее ID.
    """

    def __init__(
        self,
        confluence_client: ConfluenceClient,
        confluence_config: ConfluenceConfigSchema,
    ) -> None:
        """
        Args:
            confluence_client: Клиент Confluence, используемый для поиска страниц.
            confluence_config: Валидированная конфигурация Confluence с запасными
                               значениями ``*_name``/``*_id``.
        """
        self._client: ConfluenceClient = confluence_client
        self._config: ConfluenceConfigSchema = confluence_config

    def resolve_page_id(
        self,
        name: str | None,
        default: str | None = None,
    ) -> str | None:
        """
        Разрешает название страницы Confluence в её ID, либо возвращает ``default``.

        Args:
            name: Название страницы для поиска в настроенном Space.
            default: Значение, возвращаемое, если ``name`` не задано.

        Returns:
            ID найденной по имени страницы, либо ``default``, если имя не задано.

        Raises:
            ConfigError: Если ``name`` задан, но страница с таким названием
                         не найдена в Confluence — эту ситуацию метод не может
                         обработать самостоятельно, так как явного плана Б
                         для неё нет.
        """
        if not name:
            return default
        page = self._client.find_page(name, space=self._config.space)
        if not page:
            raise ConfigError(
                f"Страница '{name}' не найдена в пространстве '{self._config.space}'"
            )
        return page.id

    def _resolve_or_raise(
        self,
        name: str | None,
        default: str | None,
        field_label: str,
    ) -> str:
        """
        Оборачивает :meth:`resolve_page_id`, требуя непустой результат.

        Args:
            name: Название страницы для поиска в настроенном Space.
            default: Запасной ID страницы, если ``name`` не задан.
            field_label: Имя поля конфигурации для сообщения об ошибке
                         (например ``'release_docs_root_parent'``).

        Returns:
            Строка с ID страницы.

        Raises:
            ConfigError: Если ``name`` задан, но страница не найдена в Confluence,
                         либо если ни ``name``, ни ``default`` не заданы.
        """
        resolved = self.resolve_page_id(name, default)
        if not resolved:
            raise ConfigError(
                f"Необходимо указать '{field_label}_name' или '{field_label}'"
                f" в конфигурации Confluence"
            )
        return resolved

    @staticmethod
    def _merge_page_ref(
        cli_name: str | None,
        cli_id: str | None,
        config_name: str | None,
        config_id: str | None,
    ) -> tuple[str | None, str | None]:
        """
        Выбирает пару (имя, ID) для разрешения страницы: CLI или конфиг целиком.

        Args:
            cli_name: Название страницы, переданное через CLI.
            cli_id: ID страницы, переданный через CLI.
            config_name: Название страницы из конфигурации.
            config_id: ID страницы из конфигурации.

        Returns:
            Пара ``(name, id)`` из CLI, если задано хотя бы одно из значений CLI;
            иначе пара из конфигурации.
        """
        if cli_name or cli_id:
            return cli_name, cli_id
        return config_name, config_id

    def resolve_passports_root(
        self,
        name: str | None,
        page_id: str | None,
    ) -> str:
        """
        Резолвит ID корневой страницы иерархии паспортов.

        Если ``name``/``page_id`` не заданы — берёт значения из конфигурации
        Confluence как запасной вариант.

        Args:
            name: Название корневой страницы паспортов, введённое пользователем.
            page_id: ID корневой страницы паспортов, введённый пользователем.

        Returns:
            ID корневой страницы паспортов.

        Raises:
            ConfigError: Если страница не найдена ни по имени, ни по ID,
                         ни в конфигурации.
        """
        eff_name, eff_id = self._merge_page_ref(
            name,
            page_id,
            self._config.passports_root_parent_name,
            self._config.passports_root_parent_id,
        )
        return self._resolve_or_raise(eff_name, eff_id, "passports_root_parent")

    def resolve_release_parent(
        self,
        name: str | None,
        page_id: str | None,
    ) -> str:
        """
        Резолвит ID родительской страницы для релизной документации.

        Args:
            name: Название родительской страницы, введённое пользователем.
            page_id: ID родительской страницы, введённый пользователем.

        Returns:
            ID родительской страницы.

        Raises:
            ConfigError: Если ``name`` задан, но страница не найдена в Confluence,
                         либо если ни имя, ни ID не заданы ни через параметры,
                         ни в конфигурации.
        """
        eff_name, eff_id = self._merge_page_ref(
            name,
            page_id,
            self._config.release_docs_root_parent_name,
            self._config.release_docs_root_parent_id,
        )
        return self._resolve_or_raise(eff_name, eff_id, "release_docs_root_parent")

    def resolve_profile_parent(
        self,
        name: str | None,
        page_id: str | None,
    ) -> str:
        """
        Резолвит ID родительской страницы для профиль-центричной документации.

        Args:
            name: Название родительской страницы, введённое пользователем.
            page_id: ID родительской страницы, введённый пользователем.

        Returns:
            ID родительской страницы.

        Raises:
            ConfigError: Если ``name`` задан, но страница не найдена в Confluence,
                         либо если ни имя, ни ID не заданы ни через параметры,
                         ни в конфигурации.
        """
        eff_name, eff_id = self._merge_page_ref(
            name,
            page_id,
            self._config.profile_docs_root_parent_name,
            self._config.profile_docs_root_parent_id,
        )
        return self._resolve_or_raise(eff_name, eff_id, "profile_docs_root_parent")

    def resolve_single_page_parent(
        self,
        strategy_type: str,
        name: str | None,
        page_id: str | None,
    ) -> str:
        """
        Резолвит родительскую страницу для публикации одной страницы.

        Выбирает конфигурационный запасной вариант в зависимости от типа стратегии.

        Args:
            strategy_type: Тип стратегии (``'release'`` или ``'profile_centric'``).
            name: Название родительской страницы, введённое пользователем.
            page_id: ID родительской страницы, введённый пользователем.

        Returns:
            ID родительской страницы.

        Raises:
            ConfigError: Если ``name`` задан, но страница не найдена в Confluence,
                         либо если родитель не задан ни через параметры,
                         ни в конфигурации.
        """
        if strategy_type == "profile_centric":
            return self.resolve_profile_parent(name, page_id)
        return self.resolve_release_parent(name, page_id)

    def resolve_root_pages(
        self,
        passports_root_parent_name: str | None,
        passports_root_parent_id: str | None,
        release_root_page_name: str | None,
        release_root_page_id: str | None,
    ) -> tuple[str, str]:
        """
        Резолвит ID корневых страниц для паспортов и релизной документации.

        Args:
            passports_root_parent_name: Название корневой страницы паспортов
                                        или ``None`` для поиска по конфигурации.
            passports_root_parent_id: ID корневой страницы паспортов
                                      или ``None`` для поиска по конфигурации.
            release_root_page_name: Название родительской страницы релиза
                                    или ``None`` для поиска по конфигурации.
            release_root_page_id: ID родительской страницы релиза
                                 или ``None`` для поиска по конфигурации.

        Returns:
            Кортеж ``(resolved_passports_root, resolved_release_parent)``.

        Raises:
            ConfigError: Если корневая страница паспортов или родитель релиза
                         не найдены и не заданы в конфигурации.
        """
        resolved_root = self.resolve_passports_root(
            passports_root_parent_name, passports_root_parent_id
        )
        resolved_release_parent = self.resolve_release_parent(
            release_root_page_name, release_root_page_id
        )
        return resolved_root, resolved_release_parent
