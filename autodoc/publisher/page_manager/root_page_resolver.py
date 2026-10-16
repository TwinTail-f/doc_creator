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

    def resolve_parent(
        self,
        strategy_type: str,
        name: str | None,
        page_id: str | None,
    ) -> str:
        """
        Резолвит ID родительской страницы для типа публикации.

        Args:
            strategy_type: Ключ стратегии из ``registry.STRATEGIES``.
            name: Название родительской страницы, заданное пользователем.
            page_id: ID родительской страницы, заданный пользователем.

        Returns:
            ID родительской страницы.

        Raises:
            ConfigError: Если стратегия не зарегистрирована, родитель не задан или не найден.
        """
        if strategy_type not in registry.STRATEGIES:
            raise ConfigError(
                f"Стратегия {strategy_type!r} не зарегистрирована в registry.STRATEGIES: "
                "родительская страница не может быть определена"
            )
        section = getattr(self._config.strategies, strategy_type)
        return self._resolve_root_parent(
            name,
            page_id,
            section.root_parent_name,
            section.root_parent_id,
            f"strategies.{strategy_type}.root_parent",
        )
