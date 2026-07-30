"""Резолвер ссылок на корневые/родительские страницы Confluence."""

from autodoc.common.logger import logger
from autodoc.config.schemas.confluence_config import ConfluenceConfigSchema
from autodoc.exceptions import ConfigError, ConfluenceError
from autodoc.publisher.clients.confluence_client import ConfluenceClient
from autodoc.publisher.strategies import registry


class RootPageResolver:
    """
    Резолвит ссылки на корневые/родительские страницы Confluence, разрешая
    конфликты между несколькими источниками значения.
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

    def _find_page_id(self, name: str) -> str | None:
        """
        Ищет страницу по названию в настроенном Space.

        Args:
            name: Название страницы для поиска.

        Returns:
            ID найденной страницы, либо ``None``, если страница с таким
            названием не найдена.
        """
        page = self._client.find_page(name, space=self._config.space)
        return page.id if page else None

    def _page_id_exists(self, page_id: str) -> bool:
        """
        Проверяет, что страница с данным ID существует в Confluence.

        Args:
            page_id: Проверяемый ID страницы.

        Returns:
            ``True``, если страница существует, иначе ``False``.
        """
        try:
            self._client.get_page(page_id)
            return True
        except ConfluenceError:
            return False

    def _resolve_root_parent(
        self,
        cli_name: str | None,
        cli_id: str | None,
        config_name: str | None,
        config_id: str | None,
        field_label: str,
    ) -> str:
        """
        Резолвит ID родительской страницы, требуя непустой результат.

        Приоритет источников: CLI важнее конфигурации (используется
        конфигурация, только если в CLI не задано вообще ничего).
        Внутри источника приоритет ``name``->``id``.

        Args:
            cli_name: Название страницы, переданное через CLI.
            cli_id: ID страницы, переданный через CLI.
            config_name: Название страницы из конфигурации.
            config_id: ID страницы из конфигурации.
            field_label: Имя поля конфигурации для сообщения об ошибке
                         (например ``'release_docs_root_parent'``).

        Returns:
            Строка с ID страницы.

        Raises:
            ConfigError: Если ни имя, ни ID не заданы, либо заданы, но ни
                         один из них не резолвится в реальную страницу
                         Confluence.
        """
        if cli_name or cli_id:
            source_label, name, id_value = "CLI", cli_name, cli_id
        else:
            source_label, name, id_value = "Config", config_name, config_id

        if name:
            resolved_by_name = self._find_page_id(name)
            if resolved_by_name is not None:
                if id_value and resolved_by_name != id_value:
                    logger.warning(
                        f"Конфликт параметров в источнике {source_label}: "
                        f"'{field_label}_name'={name!r} и '{field_label}'="
                        f"{id_value!r} указывают на разные страницы "
                        f"Confluence (id по имени: {resolved_by_name}). "
                        f"Используется значение '{field_label}_name'."
                    )
                return resolved_by_name

            if id_value and self._page_id_exists(id_value):
                logger.warning(
                    f"В источнике {source_label} '{field_label}_name'="
                    f"{name!r} не резолвится в существующую страницу "
                    f"Confluence в пространстве '{self._config.space}'. "
                    f"Используется запасное значение '{field_label}'="
                    f"{id_value!r}."
                )
                return id_value

            raise ConfigError(
                f"Страница '{name}' не найдена в пространстве "
                f"'{self._config.space}', а запасной '{field_label}' не "
                f"задан либо тоже указывает на несуществующую страницу"
            )

        if id_value:
            if not self._page_id_exists(id_value):
                raise ConfigError(
                    f"Страница с ID='{id_value}', указанным для "
                    f"'{field_label}', не найдена в Confluence"
                )
            return id_value

        raise ConfigError(
            f"Необходимо указать '{field_label}_name' или '{field_label}'"
            f" в конфигурации Confluence"
        )

    def resolve_passports_root(
        self,
        name: str | None,
        page_id: str | None,
    ) -> str:
        """
        Резолвит ID корневой страницы иерархии паспортов.

        Если ``name``/``page_id`` не заданы — берёт значения из
        ``confluence_config.strategies.passports`` как запасной вариант.

        Args:
            name: Название корневой страницы паспортов, введённое пользователем.
            page_id: ID корневой страницы паспортов, введённый пользователем.

        Returns:
            ID корневой страницы паспортов.
        """
        section = self._config.strategies.passports
        return self._resolve_root_parent(
            name,
            page_id,
            section.root_parent_name,
            section.root_parent_id,
            "strategies.passports.root_parent",
        )

    def resolve_single_page_parent(
        self,
        strategy_type: str,
        name: str | None,
        page_id: str | None,
    ) -> str:
        """
        Резолвит родительскую страницу для публикации одной страницы.

        Тип стратегии проверяется по ``registry.STRATEGIES``: сначала — что стратегия
        вообще зарегистрирована, затем — что ``IS_SINGLE_PAGE`` у неё ``True`` (т.е. она
        в принципе имеет понятие "родительская страница по секции конфига"). Секция
        конфига берётся по имени, совпадающему со ``strategy_type`` дословно
        (``confluence_config.strategies.<strategy_type>``) — без отдельной таблицы
        соответствия: имена секций ``StrategiesConfig`` специально выбраны такими же,
        как ключи ``registry.STRATEGIES``.

        Args:
            strategy_type: Тип стратегии, зарегистрированный в ``registry.STRATEGIES``
                           с ``IS_SINGLE_PAGE = True`` (например ``'release'`` или
                           ``'profile_centric'``).
            name: Название родительской страницы, введённое пользователем.
            page_id: ID родительской страницы, введённый пользователем.

        Returns:
            ID родительской страницы.

        Raises:
            ConfigError: Если ``strategy_type`` не зарегистрирован в
                ``registry.STRATEGIES``, либо зарегистрирован, но
                ``IS_SINGLE_PAGE`` у него ``False`` (например ``'passports'``) —
                такая стратегия не имеет родительской страницы, резолвируемой по
                этой схеме.
        """
        strategy_cls = registry.STRATEGIES.get(strategy_type)
        if strategy_cls is None or not strategy_cls.IS_SINGLE_PAGE:
            raise ConfigError(
                f"Стратегия {strategy_type!r} не поддерживает резолвинг родительской "
                "страницы одностраничной публикации (не зарегистрирована в "
                "registry.STRATEGIES либо IS_SINGLE_PAGE=False)"
            )
        section = getattr(self._config.strategies, strategy_type)
        return self._resolve_root_parent(
            name,
            page_id,
            section.root_parent_name,
            section.root_parent_id,
            f"strategies.{strategy_type}.root_parent",
        )

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

        """
        resolved_root = self.resolve_passports_root(
            passports_root_parent_name, passports_root_parent_id
        )
        resolved_release_parent = self.resolve_single_page_parent(
            "release", release_root_page_name, release_root_page_id
        )
        return resolved_root, resolved_release_parent
