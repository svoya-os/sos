# {{ project.name }}

Программа на [UpsiL](https://github.com/svoya-os/upsil), языке СОС для работы с нейросетями.
Создана командой `sos new --template upsil`.

```sh
sos models serve            # локальная модель, если ещё не запущена
sos run main.upl "rust"     # заголовок окружения; прогресс — на панели СОС
upsil test                  # тесты из tests/
upsil check main.upl        # найти ошибки без запуска
```

* `main.upl` — программа, `prompts.upl` — вопросы к модели и разбор ответов, `tests/` — проверки.
* Модель: сервер `sos models serve` (`http://127.0.0.1:8080/v1`). Другой сервер или модель — в `.env`
  (`UPSIL_LLM_URL`, `UPSIL_LLM_MODEL`); `sos run` передаёт их программе.
* Нейросети (`import nn`) нужен PyTorch: `uv add torch`. Колёса под эту машину (`{{ gpu.backend }}`,
  {{ gpu.detected }}) уже указаны в `pyproject.toml`, а `sos run` сам запустит программу в `.venv` проекта.
* Данные и модели: `data/` → `{{ paths.datasets }}`, `models/` → `{{ paths.ai }}` (общее хранилище, ничего не копируется).
* Язык: `/usr/share/doc/upsil` (спецификация, учебник, примеры). Джексон тоже знает UpsiL — попросите его
  «напиши на упсиле…».

---

An [UpsiL](https://github.com/svoya-os/upsil) program (the SOS language for AI scripts): `sos run main.upl`
runs it, `upsil test` runs the tests, `uv add torch` enables `import nn`, and the docs are in `/usr/share/doc/upsil`.
