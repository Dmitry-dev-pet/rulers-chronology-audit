# Проверка исторической таблицы правителей

Приватный исследовательский проект по плакату **«Правители государства с древнейших времен»**. Начат 10 октября 2026 года.

## Советский период: актуальная версия

**[Три параллельные хронологии, 1917–1991](research/soviet-parallel-chronology.md): партия, правительство, высшие государственные органы.**

[Машиночитаемые данные JSON](data/soviet-parallel-chronology.json) · [Источники и границы проверки](research/soviet-parallel-sources.md) · [Уточнения к первому разбору](research/soviet-period-corrections.md).

Новая версия уточняет коллегиальное устройство ЦИК, совмещение должностей, три замещения Кузнецовым и неоднозначные переходы 1923, 1953 и 1991 годов. Она имеет приоритет перед сокращёнными формулировками первоначального разбора. Не все персональные назначения независимо проверены по оригиналам актов; спорные и предварительные записи явно отмечены.

## Оригинальное фото

**[Открыть исходную фотографию (Google Drive)](https://drive.google.com/file/d/1rHAcVH5_UuuqWRX0L76K7eay0KxYCt8u/view)** · [Папка проекта в Google Drive](https://drive.google.com/drive/folders/1ztJMRaG12lpi3UOOqyu2VP3EiWntwNW6).

- Имя файла: `1000428575.jpg`
- Формат и разрешение: JPEG, 1152 × 1536
- Размер: **464 782 байта**
- SHA-256: `6c487e9427658f711cb41b930db2fadd06bb4b921423ab0b1b5bab4416a1c6ee`
- **Проверка завершена**: исходный файл загружен в Google Drive, затем скачан обратно и идентифицирован по SHA-256.
- **Доступ к фото закрытый:** ссылка Google Drive требует разрешения владельца. Фото не делалось общедоступным.

По договорённости с пользователем **бинарное фото хранится в Google Drive**, а **в GitHub — исследовательские данные, ссылки и контрольная сумма**. Загружать JPEG в Git или открывать публичный доступ не требуется. Подробности: [GOOGLE_DRIVE_SOURCE.md](assets/original/GOOGLE_DRIVE_SOURCE.md), [photo-metadata.json](assets/original/photo-metadata.json).

## Содержание проекта

- [data/poster-transcription.tsv](data/poster-transcription.tsv) — буквальная предварительная расшифровка **106 строк** (53 в каждой колонке), включая исходные ошибки.
- [data/section-markers.md](data/section-markers.md) — названия династий, служебные строки и подписи столиц.
- [research/initial-audit.md](research/initial-audit.md) — первоначальные 23 замечания.
- Первый советский разбор: [текст](research/soviet-period-audit.md), [реестр 10 строк](data/soviet-period-review.csv), [его источники](research/soviet-period-sources.md). Читать вместе с [уточнениями](research/soviet-period-corrections.md).
- [research/source-index.md](research/source-index.md) — 25 исходных ссылок; каждую проверять при дальнейшем использовании.
- [data/claim-register.csv](data/claim-register.csv) — первоначальный реестр спорных утверждений.
- [docs/context.md](docs/context.md) — решение о хранении оригинала и контекст обсуждения.
- [NEXT_STEPS.md](NEXT_STEPS.md) — общий план исследования; советские параллельные хронологии теперь подготовлены, их источниковедческая доработка продолжается.
- [scripts/verify_original_photo.py](scripts/verify_original_photo.py) — проверка SHA-256 локальной копии.

**Полная независимая проверка всех 106 строк не завершена.** Не смешивать буквальное чтение плаката, справочную хронологию должностей и интерпретацию фактической политической власти.

Задачи: [#1 — архивирование оригинала (выполнено)](https://github.com/Dmitry-dev-pet/rulers-chronology-audit/issues/1), [#2 — проверка 106 строк (открыта)](https://github.com/Dmitry-dev-pet/rulers-chronology-audit/issues/2).
