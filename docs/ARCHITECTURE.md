# Архитектура и расширение autodoc

Документ для тех, кто дорабатывает сам проект: как он устроен, как добавить новый тип
публикуемой страницы, как запускать тесты. Как пользоваться инструментом (конфиги, команды,
флаги) — в [README](../README.md).

Порядок изложения: сначала общая картина и устройство репозитория, затем общие слои,
после них парсер и паблишер (оба описаны по одной схеме), затем пошаговая инструкция по
расширению и, наконец, правила разработки и тестов.

## Оглавление

- [Обзор](#обзор)
- [Структура репозитория](#структура-репозитория)
- [Общие слои](#общие-слои)
- [Парсер](#парсер)
- [Паблишер](#паблишер)
  - [Как публикуется страница](#как-публикуется-страница)
  - [Стратегии и реестр](#стратегии-и-реестр)
  - [План публикации и publish all](#план-публикации-и-publish-all)
  - [Рендеринг: шаблоны и стили](#рендеринг-шаблоны-и-стили)
- [Как добавить новую страницу](#как-добавить-новую-страницу)
- [Разработка и тесты](#разработка-и-тесты)

---

## Обзор

autodoc работает в две независимые стадии, каждая запускается отдельной командой CLI:

```
TFS (манифесты, опции, Docker)  ┐
Conan (conan graph info)        ├─►  parse  ─►  data/parsed_data.json  ─►  publish  ─►  Confluence
Artifactory (проверка ссылок)   ┘
```

1. **`parse`** собирает данные о компонентах платформы и сохраняет их в
   `data/parsed_data.json`.
2. **`publish ...`** читает этот файл и публикует страницы в Confluence.

Из этого вытекают принципы, на которых держится остальной код:

- **Стадии не знают друг о друге.** `parser` ничего не знает о Confluence, `publisher` — о
  TFS и Conan. Единственная точка соприкосновения — формат `parsed_data.json`, то есть
  модели из `autodoc/models/`.
- **Расширение — через регистрацию, а не через правку ядра.** Типы страниц подключаются
  записью в явном реестре и узлом в декларативном плане (см. раздел про
  [добавление страницы](#как-добавить-новую-страницу)); сквозной идентификатор типа — строковый
  ключ стратегии.
- **Одна точка изменения моделей.** В парсере доменные объекты мутирует только `DataEnricher`,
  шаги пайплайна обмениваются данными лишь через `PipelineContext`.

Рядом с проектом (не внутри пакета `autodoc/`) во время работы CLI появляются рабочие
директории:

```
<base-dir>/
├── data/  — data/parsed_data.json (результат parse, вход для publish)
└── logs/  — файлы логов по одному на запуск parse/publish (см. «Логирование» в README)
```

## Структура репозитория

```
.
├── autodoc/            — исходный код
├── configs/examples/   — примеры конфигов (yaml и json); рабочие конфиги лежат в configs/
├── docs/               — документация для разработчиков (этот файл)
├── tests/              — тесты; структура повторяет структуру autodoc/
├── README.md           — руководство пользователя
├── pyproject.toml, setup.cfg, pytest.ini — настройки пакета, линтера и тестов
└── conftest.py         — корневая конфигурация pytest
```

Пакеты внутри `autodoc/`:

| Пакет | Роль | Подробнее |
|-------|------|-----------|
| `cli/` | Команды и группы Click; тонкий слой, который связывает конфиг, парсер и паблишер | [Общие слои](#общие-слои) |
| `config/` | Загрузка конфигов (JSON/YAML) и pydantic-схемы | [Общие слои](#общие-слои) |
| `models/` | Доменные модели; формат `parsed_data.json` | [Общие слои](#общие-слои) |
| `common/` | Логгер, параллельный исполнитель, HTTP-сессия с retry | [Общие слои](#общие-слои) |
| `exceptions.py` | Иерархия исключений проекта | [Общие слои](#общие-слои) |
| `parser/` | Сбор данных из TFS, Conan, Docker, Artifactory | [Парсер](#парсер) |
| `publisher/` | Публикация в Confluence | [Паблишер](#паблишер) |

Допустимые направления зависимостей:

- `parser` и `publisher` не импортируют друг друга;
- `models`, `common` и `exceptions` не зависят от `parser` и `publisher` — их используют все;
- `cli` — единственный слой, который знает про оба: он запускает парсер, сохраняет
  результат и передаёт его паблишеру;
- единственное исключение из «`config` ничего не знает о стадиях»: схема конфига Confluence
  импортирует `publisher/strategies/publish_plan.py`, чтобы допустимые типы публикации
  выводились из плана, а не дублировались в схеме.

## Общие слои

**`cli/`** — команды Click: `parse`, группа `publish` (по команде на тип страницы и
`publish all`), `config`, `info`, `logs`. Команды не содержат бизнес-логики: загружают
конфиг, создают парсер или паблишер и печатают результат. Общие операции вынесены в
`helpers.py` (создание паблишера, загрузка `parsed_data.json`, граница обработки ошибок),
значения по умолчанию и имена шаблонов — в `constants.py`, контекст запуска — в `context.py`.
Команды публикации одной страницы делят логику через `publish/single_page.py`.

**`config/`** — `manager.py` читает конфиги из JSON и YAML; `schemas/` содержит pydantic-схемы
`ParserConfigSchema` и `ConfluenceConfigSchema`. Схемы валидируют конфиг при загрузке и
формулируют понятные сообщения об ошибках.

**`models/`** — доменные модели: компонент, релиз, профиль сборки, вариант Conan, опции и
итоговый `ParsedResult`. Именно они сериализуются в `parsed_data.json`, поэтому изменение
модели — это изменение контракта между парсером и паблишером.

**`common/`** — `logger.py` (единый логгер для обеих стадий), `parallel_executor.py`
(параллельное выполнение задач через `ThreadPoolExecutor`), `retryable_session.py` (HTTP с
повторами и экспоненциальной паузой).

**`exceptions.py`** — иерархия от `DocGeneratorError`: `ConfigError`, `NetworkError`,
`ParsingError`, `PublishError`/`ConfluenceError`, `ValidationError`. Команды CLI ловят их на
границе и завершаются с понятным сообщением вместо трейсбека.

## Парсер

**Назначение.** По конфигу парсера собрать данные о компонентах платформы из TFS, обогатить
их через `conan graph info`, проверить ссылки в Artifactory и вернуть `ParsedResult`.
Сохраняет результат в `data/parsed_data.json` команда `parse` (сам парсер пишет файлы только
для промежуточных снимков по флагу `--save-intermediate`).

**Структура пакета.**

```
parser/
├── parser.py     — ComponentParser: собирает цепочку шагов, запускает её, возвращает ParsedResult
├── pipeline/     — PipelineContext: единственный канал передачи состояния между шагами
├── steps/        — шаги пайплайна
├── fetchers/     — получение сырых данных (манифесты, опции, Docker, Conan)
├── parsers/      — чистый разбор полученного текста в доменные модели, без сети
├── enrichment/   — DataEnricher: единственное место мутации доменных моделей
├── conan/        — запуск conan graph info: задачи, раннер, окружение, переопределения профилей
├── clients/      — HTTP-клиенты TFS и Artifactory
└── utils/        — чтение .properties
```

**Как это работает.** Парсер выполняет шаги последовательно:

```
ManifestStep → OptionsResolveStep → ConanEnrichStep
    → DockerResolveStep → ArtifactoryValidationStep → FinalizeStep
```

Каждый шаг — изолированный объект, общается с остальными только через `PipelineContext`.
`ConanEnrichStep` и `ArtifactoryValidationStep` убираются из цепочки флагами
`--skip-conan` / `--skip-validation`.

**Правила, на которых держится пакет.**

- Фетчеры двухфазовые: `configure(ctx)` затем `fetch()`; зависимости приходят из контекста.
- Парсеры не ходят в сеть — они только превращают текст в модели, поэтому легко тестируются.
- Граф зависимостей однонаправленный: `pipeline/context.py` не зависит от `steps/` и
  `fetchers/`, а они зависят от него.
- Модели меняет только `DataEnricher`; шаги вызывают его методы, но не правят объекты сами.

## Паблишер

**Назначение.** Прочитать `ParsedResult` и опубликовать страницы в Confluence: одну страницу
на тип (релиз, профили, комплекты встраивания) или иерархию (паспорта компонентов).

**Структура пакета.**

```
publisher/
├── publisher.py     — DocumentPublisher: фасад, создаёт и запускает стратегии
├── strategies/      — стратегии публикации, реестр STRATEGIES, план PUBLISH_PLAN
├── converters/      — ParsedResult → view-model (словарь для шаблона)
├── rendering/       — Jinja2-шаблоны, макросы, стили, DocumentBuilder
├── page_manager/    — родительские страницы, иерархия, карта ID паспортов
├── clients/         — клиент Confluence REST API
├── legacy_content/  — работа с содержимым ранее опубликованных страниц
└── view_models/     — типы view-model, общие для конвертеров
```

### Как публикуется страница

Публикацию одной страницы собирают четыре части, у каждой своя роль:

| Часть | Где лежит | Что делает |
|-------|-----------|------------|
| Конвертер | `publisher/converters/` | Превращает `ParsedResult` во view-model — словарь, который видит шаблон |
| Шаблон | `publisher/rendering/templates/` | Jinja2-шаблон, выдающий Confluence Storage Format |
| Стратегия | `publisher/strategies/` | Склеивает конвертер, шаблон и клиент Confluence; публикует страницу или иерархию |
| Секция конфига | `config/schemas/confluence_config.py` | Заголовок страницы и адрес родителя для этого типа |

Путь одной страницы: `DocumentPublisher` создаёт стратегию по ключу →
стратегия вызывает конвертер → `DocumentBuilder` рендерит шаблон → клиент публикует
страницу под нужным родителем.

### Стратегии и реестр

Стратегии регистрируются явным словарём `STRATEGIES` в
`autodoc/publisher/strategies/registry.py` и создаются по строковому ключу функцией
`create_strategy()`. Ключ стратегии — сквозной идентификатор типа: он же имя секции в
`strategies:` конфига (`getattr(config.strategies, key)` — без таблицы соответствия) и имя
узла в плане публикации.

| Стратегия | Команда CLI | Описание |
|-----------|-------------|----------|
| `release` | `publish release` | Одна страница: все компоненты с их релизами и профилями |
| `profile_centric` | `publish profile` | Одна страница: вид по профилям сборки → каналам → компонентам |
| `passports` | `publish passports` | Иерархия страниц: Корень → Компонент → Версия |
| `kit_pinned` | `publish kit-pinned` | Одна страница: точные Conan-ссылки закреплённых версий по каналам |
| `kit_latest` | `publish kit-latest` | Одна страница: ссылки на последние сборки компонентов по каналам |

Иерархия классов стратегий:

```
BasePublishStrategy              — общий каркас: рендер, минификация, публикация; execute() абстрактен
├── PassportsStrategy            — иерархия страниц (IS_SINGLE_PAGE = False)
└── SinglePagePublishStrategy    — шаблонный поток convert → enrich → publish одной страницы
    ├── ReleasePageStrategy
    ├── ProfileCentricPageStrategy
    └── EmbeddingKitPageStrategy — база для страниц комплекта встраивания (CONVERTER_CLS)
        ├── KitPinnedPageStrategy
        └── KitLatestPageStrategy
```

### План публикации и publish all

Порядок и зависимости типов в `publish all` задаёт декларативный `PUBLISH_PLAN` в
`autodoc/publisher/strategies/publish_plan.py`. Узел `PublishNode(key, parent_from)` говорит,
в каком порядке публикуется тип и откуда берётся его родитель:

- `parent_from=None` — родитель задан секцией конфига (`root_parent_name` / `root_parent_id`);
- `parent_from="<ключ>"` — страница публикуется дочерней к странице другого типа
  (сейчас так публикуется `profile_centric` — под страницей `release`). Родитель обязан
  стоять в плане раньше потомка и быть одностраничным; если он не опубликован, потомок
  пропускается с ошибкой в отчёте.

`DocumentPublisher.publish_all` выполняет выбранные в `publish_all.targets` типы строго в
порядке плана. Порядок, в котором типы перечислены в конфиге, ни на что не влияет. Порядок
«паспорта → релиз» важен: после первого шага генерируется карта ID страниц паспортов
(`passport_pages.json`), которую `release` использует для вставки ссылок.

Из плана выводится и валидация конфига: допустимые значения и значение по умолчанию для
`publish_all.targets`, проверка «дочерний тип требует родителя в списке», проверка наличия
`root_parent_*` у выбранных типов. Править эти проверки при добавлении типа не нужно.

### Рендеринг: шаблоны и стили

**Jinja2-шаблоны** хранятся в `autodoc/publisher/rendering/templates/`. Используется
Confluence Storage Format (AUI-макросы, вкладки).

```
autodoc/publisher/rendering/templates/
├── release_doc.jinja2        — страница релиза (компонентный вид)
├── profile_centric.jinja2    — профиль-центричный вид
├── component_passport.jinja2 — паспорт компонента
├── embedding_kit.jinja2      — комплект для встраивания (kit-pinned / kit-latest)
└── _platform_intro.jinja2    — вспомогательный partial (вводный блок платформы)
```

**Стили и макросы.** Confluence REST API не позволяет публиковать CSS вместе со страницей,
поэтому стили вынесены в общую таблицу стилей пространства (как её подключить — см. «Стили
страниц (CSS)» в README). Исходники стилей — в `autodoc/publisher/rendering/styles/`:
`_styles_base.jinja2` (общие) и `_styles_passport.jinja2` (специфичные для паспорта).
Повторяющиеся фрагменты разметки вынесены в макросы
`autodoc/publisher/rendering/macros/_macros.jinja2`.

## Как добавить новую страницу

Ниже — полный список мест, которые нужно тронуть. Все шаги нужны для одностраничного типа;
для иерархии страниц (как `passports`) отличаются шаги 3, 5 и 7 — см. примечания в них.
В примерах новый тип называется `my_page`, команда — `publish my-page`.

Сначала определите три вещи:

1. **Одна страница или иерархия.** Одна страница — наследник `SinglePagePublishStrategy`;
   иерархия — наследник `BasePublishStrategy` с собственным `execute()` (образец —
   `PassportsStrategy`).
2. **Откуда берётся родитель.** Либо из секции конфига (`parent_from=None`, пользователь
   задаёт `root_parent_name` / `root_parent_id`), либо это страница-потомок другого типа
   (`parent_from="release"`).
3. **Какое место в порядке публикации.** Если странице нужны данные другого типа (например,
   карта ссылок на паспорта), она должна идти после него.

### Шаг 1. Конвертер

Класс в `autodoc/publisher/converters/`, наследник `BaseDataConverter`. Обязателен
`convert(data: ParsedResult) -> dict` — он возвращает view-model, из которого строится страница.

- Для страниц вида «таблица Conan-ссылок по каналам» есть готовая база `BaseKitConverter`:
  достаточно задать `VERSION_COLUMN_TITLE` и реализовать `_build_row()` (образец —
  `KitLatestConverter`).
- Если на странице нужны ссылки на паспорта, переопределите `enrich_with_passport_links()`
  и `wants_passport_links`; иначе базовые реализации ничего не делают и карта паспортов не
  загружается.

### Шаг 2. Шаблон

Если подходит существующий шаблон (например, `embedding_kit.jinja2`), этот шаг пропускается.
Иначе — новый файл `autodoc/publisher/rendering/templates/my_page.jinja2` в Confluence Storage
Format. View-model доступна в шаблоне как переменная `data`. Общие стили и макросы
подключаются из `rendering/styles/` и `rendering/macros/` (см. шаблоны-образцы в разделе
[«Рендеринг: шаблоны и стили»](#рендеринг-шаблоны-и-стили)). Новый CSS-класс нужно добавить в
`_styles_base.jinja2` и сообщить владельцу пространства, что таблицу стилей пространства
нужно обновить (см. «Стили страниц (CSS)» в README).

### Шаг 3. Стратегия

Файл `autodoc/publisher/strategies/my_page_strategy.py`.

Одностраничный тип — наследник `SinglePagePublishStrategy`:

- `DEFAULT_TEMPLATE` — имя шаблона из шага 2;
- `__init__`: `kwargs.setdefault("template_name", self.DEFAULT_TEMPLATE)` и передача конвертера
  в `super().__init__(converter=converter or self._make_converter(...), **kwargs)`;
- `_make_converter()` — создаёт конвертер из шага 1;
- `IS_SINGLE_PAGE` уже `True` в `SinglePagePublishStrategy`.

Для страниц комплекта встраивания достаточно наследоваться от `EmbeddingKitPageStrategy` и
задать `CONVERTER_CLS` (образец — `kit_latest_strategy.py`, всего несколько строк).

Если стратегии нужны параметры из конфига помимо `page_title`, переопределите классовый
метод `kwargs_from_config(config, key)`: он возвращает словарь аргументов конструктора
(без `parent_id`). Базовая реализация `SinglePagePublishStrategy` отдаёт только
`page_title` секции с именем `key`.

Иерархия страниц: наследник `BasePublishStrategy`, `IS_SINGLE_PAGE = False`, реализация
`execute()`; такая стратегия не публикуется через `publish_single_page`.

### Шаг 4. Реестр

Добавить строку в `STRATEGIES` в `autodoc/publisher/strategies/registry.py`:

```python
STRATEGIES: dict[str, type[BasePublishStrategy]] = {
    ...
    "my_page": MyPageStrategy,
}
```

Ключ (`"my_page"`) дальше должен совпасть с именем секции конфига и ключом узла плана.

### Шаг 5. Секция конфига

В `autodoc/config/schemas/confluence_config.py`:

1. Класс полей — наследник `SinglePageDocsFields` (адресация родителя + `page_title`) со своим
   значением `page_title` по умолчанию:

   ```python
   class MyPageDocsFields(SinglePageDocsFields):
       """Поля стратегии my_page — со своим дефолтным заголовком."""

       page_title: str = Field(
           default="Заголовок по умолчанию",
           description="Заголовок страницы ...",
       )
   ```

   Для иерархии без собственного заголовка используется `RootParentFields` (как у `passports`).
2. Поле в `StrategiesConfig` **с именем, дословно равным ключу из реестра**:
   `my_page: MyPageDocsFields = Field(default_factory=MyPageDocsFields)`.

Дальше схема сделает всё сама: секция попадёт в проверку «явно указанная секция обязана
иметь `root_parent_*`», а тип — в допустимые значения `publish_all.targets`.

### Шаг 6. План публикации

Добавить узел в `PUBLISH_PLAN` (`autodoc/publisher/strategies/publish_plan.py`) в той позиции,
в которой тип должен публиковаться:

```python
PUBLISH_PLAN: tuple[PublishNode, ...] = (
    ...
    PublishNode("my_page"),                          # родитель — из секции конфига
    # PublishNode("my_page", parent_from="release"), # либо дочерняя страница типа release
)
```

После этого `publish all` выполняет новый тип без правок в `DocumentPublisher.publish_all`
и в `PublishAllConfig`: список допустимых и значение по умолчанию для
`publish_all.targets`, проверки родителей и сообщения об ошибках строятся из плана.

### Шаг 7. CLI-команда

1. **Константы** в `autodoc/cli/constants.py`: имя шаблона берётся из стратегии
   (`MY_PAGE_TEMPLATE = MyPageStrategy.DEFAULT_TEMPLATE`) и заголовок по умолчанию
   (`DEFAULT_MY_PAGE_PAGE_TITLE`).
2. **Команда** — новый файл `autodoc/cli/commands/publish/my_page.py`. Для одностраничного
   типа вся логика уже есть в `single_page.py`:
   - без ссылок на паспорта — `@kit_page_options` и `run_kit_page_command` (образец —
     `kit_latest.py`);
   - со ссылками на паспорта и флагом `--no-passport-links` — `@single_page_options` и
     `run_single_page_command` (образец — `release.py`).

   Иерархию страниц оформляют отдельной командой со своими флагами (образец — `passports.py`).
3. **Регистрация:** импорт и `publish.add_command(publish_my_page)` в
   `autodoc/cli/commands/publish/__init__.py`.

Команда `publish all` ничего про новый тип «знать» не должна — ей достаточно плана.

### Шаг 8. Примеры конфигов

Добавить секцию `strategies.my_page` в `configs/examples/confluence_config.yaml` и
`configs/examples/confluence_config.json` (с пояснением про `root_parent_*` и
`page_title`) и, если в примерах перечислены значения `publish_all.targets`, дописать
новый ключ в перечисление.

### Шаг 9. Документация

В [README](../README.md): строки новой секции в таблицах параметров («Конфигурация
публикации в Confluence»), описание команды `publish my-page` в разделе «Команды CLI» и
пункт в оглавлении; в этом документе — строка в таблице стратегий и, если менялась,
иерархия классов.

### Шаг 10. Тесты

Часть проверок срабатывает сама, часть нужно дописать.

**Срабатывают автоматически:**

- `test_publish_plan_keys_match_registry_and_config_sections`
  (`tests/unit/publisher/strategies/test_publish_plan.py`) — падает, если ключ есть не во
  всех трёх местах: реестр, план, `StrategiesConfig`. Это страховка от забытого шага 4, 5 или 6;
- остальные тесты плана (родитель раньше потомка и одностраничный, порядок по умолчанию для
  `publish_all.targets`);
- тесты, где набор типов выводится из плана или реестра (`test_publisher.py`,
  `test_validators.py`, `test_strategy_kwargs.py`).

**Нужно написать:**

- конвертер — `tests/unit/publisher/converters/test_my_page_converter.py`;
- стратегия — `tests/unit/publisher/strategies/test_my_page_strategy.py` (образцы —
  `test_kit_latest_strategy.py`, `test_release_strategy.py`);
- шаблон — прогон через `DocumentBuilder` (образец — `test_production_templates.py`);
- CLI-команда — `tests/unit/cli/test_publish_my_page_command.py` (образцы —
  `test_publish_kit_commands.py`, `test_publish_single_page.py`).
  Подмены `make_publisher` и `load_parsed_data` уже есть в `tests/unit/cli/conftest.py`
  (фикстуры `mock_publisher`, `make_publisher_mock`, `load_parsed_data_mock`); в тестовом
  модуле достаточно переопределить фикстуру `command_module`, вернув путь модуля команды;
- строку нового типа в таблицу ожиданий `test_registry.py` (признак одностраничности и класс
  стратегии): там ожидания для каждого типа заданы явно.

### Чек-лист

- [ ] Конвертер и шаблон
- [ ] Стратегия
- [ ] Строка в `STRATEGIES`
- [ ] Класс полей и поле в `StrategiesConfig` (имя поля = ключ реестра)
- [ ] Узел в `PUBLISH_PLAN`
- [ ] Константы, команда и `add_command` в CLI
- [ ] Секция в `configs/examples/` (yaml и json)
- [ ] README и этот документ
- [ ] Тесты (конвертер, стратегия, шаблон, команда)

## Разработка и тесты

### Установка и запуск

```bash
pip install -e ".[dev]"
python -m pytest
```

`pytest.ini` подключает измерение покрытия (`--cov=autodoc`, HTML-отчёт в `htmlcov/`).

### Структура тестов

Дерево `tests/unit/` повторяет дерево `autodoc/`: `cli/`, `common/`, `config/`, `models/`,
`parser/`, `publisher/`. Тесты помечены маркерами по смыслу проверки:

| Маркер | Что проверяет |
|--------|---------------|
| `business_logic` | правила предметной области |
| `integration` | несколько реальных объектов вместе |
| `contract` | совместимость интерфейсов |
| `infrastructure` | механика фреймворков, subprocess, HTTP |

### Общие фикстуры и фабрики

Фикстуры, общие для пакета тестов, лежат в `conftest.py` этого пакета и видны только в нём
(например, в `tests/unit/cli/conftest.py` — `configs_dir`, `mock_publisher`,
`make_publisher_mock`, `load_parsed_data_mock`). Обычные функции-фабрики и константы
(не фикстуры) лежат рядом в `utils.py` и импортируются явно.

### Соглашения по оформлению

- Строки не длиннее 100 символов (`setup.cfg`).
- Докстринги на русском. Многострочный докстринг: открывающие `"""` на отдельной строке,
  текст со следующей, закрывающие `"""` на отдельной строке. Однострочный — одной строкой,
  с точкой в конце.
