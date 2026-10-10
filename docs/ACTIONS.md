# GitHub Actions и публикация исторического атласа 1417–1991

`.github/workflows/soviet-audit.yml` — название legacy workflow; он теперь проверяет **весь** исторический атлас.

```sh
python3 -m unittest discover -s tests -v
python3 scripts/soviet_audit.py --revision local-check
python3 -m scripts.extend_century
python3 -m scripts.extend_romanovs
python3 -m scripts.extend_muscovy
```

Четыре независимых источниковых слоя записывают исходные пояснения отдельно от буквального текста плаката. Тесты сверяют первоначальную транскрипцию 106 строк, 48 печатных строк в опубликованной части, ссылки и структуру власти. CI **не** доказывает историческую достоверность каждого утверждения.

После успешных тестов генератор собирает статический HTML/CSS/JS, хронологию JSON, реестр источников, **семь CSV** (включая `muscovy.csv`, `romanov.csv`, `imperial.csv`), README, отчёт и контрольные суммы, всего **15 разрешённых текстовых файлов**.

GitHub Pages публикует результат только из `main`, с ограниченными `contents:read`, `pages:write`, `id-token:write`. На pull request деплой не выполняется. Проверяются запрет исходного JPEG и отсутствие ссылок на закрытый Drive. GitHub-hosted Ubuntu, без Mac, персональных токенов, LLM и браузера.

Результат: https://dmitry-dev-pet.github.io/rulers-chronology-audit/ .
