# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

# MedSeal — контекст проекта

**MedSeal** — веб-платформа, защищающая медицинские снимки (рентген, КТ) и медицинский ИИ от подделок.
Проект для National AI Hackathon (Наманган, 2026), трек «Медицина», официальная задача №6
(стандарты этики и безопасности ИИ для анализа рентгена/КТ).

Питч в одну строку: *«Печать и антивирус для медицинских снимков: подтверждаем целостность снимка и измеряем, насколько легко обмануть ИИ, который его читает».*

## Текущее состояние репозитория

- Работа поделена: backend ведёт владелец репозитория, frontend — второй разработчик. Контракт между ними — `docs/API.md`; любое изменение ответа API сразу отражать там.
- **Честность AI-результатов:** детектор и щит дают вероятностные предупреждения и показываются как экспериментальные/условные; окончательное клиническое решение принимает врач. Паспорт — это исследовательская оценка устойчивости, а не разрешение на клиническое применение.
- Backend готов: устройства, печать, проверка, реестр с hash-chain, `/stats`, краш-тест, щит, паспорт + PDF. `app/ai/hooks.py` — точка подключения ИИ к `/verify`: щит и детектив подключены (детектив возвращает `null`, пока нет весов `backend/weights/detective.pt` — они в .gitignore, обучение: `python -m scripts.train_detective`, ~20 мин).
- **Аутентификация записи (harden v2, P0-1):** `POST /devices` и `/devices/{id}/revoke` требуют `Authorization: Bearer <MEDSEAL_ADMIN_TOKEN>`. `POST /seal` требует `Authorization: Bearer <device token>` — устройство определяется по токену, поля `device_id` в форме больше нет. Токен устройства выдаётся один раз при создании (`POST /devices` возвращает `token` в ответе), хранится только его sha256 (`devices.token_hash`, см. `app/auth.py`). Демо-устройство создаётся напрямую в БД без HTTP: `python -m scripts.create_demo_device`. Фронтенд никогда не хранит токен в `NEXT_PUBLIC_*` — печать идёт через серверный роут `by_billy/frontend/src/app/api/seal/route.ts`, который берёт токен из `MEDSEAL_DEVICE_TOKEN` (`.env.local`, только на сервере Next.js).
- **P1-01 (audit remediation):** страница `/seal` и роуты `/api/seal`, `/api/crash-test`, `/api/passport` дополнительно закрыты HTTP Basic Auth на уровне Next.js: `by_billy/frontend/src/proxy.ts` (Proxy — так в Next 16 называется бывший Middleware, работает на Node.js runtime по умолчанию) перехватывает запрос первым, каждый route handler проверяет ещё раз (`src/lib/gatewayAuth.ts`). Креды — `MEDSEAL_GATEWAY_USER`/`MEDSEAL_GATEWAY_PASSWORD` в `.env.local`; без них — `503` (fail closed). `/api/seal` также отклоняет тела > 50 МБ (`413`) по заголовку `Content-Length`, до чтения тела.
- **FE-01 (audit remediation):** клиентские страницы регистрации/входа (`register`, `login`) и `lib/auth.ts` удалены — они были декоративными (пароль никогда не проверялся). Реальная защита — HTTP Basic Auth из P1-01 на шлюзовых/админских действиях.
- Паспорт (`app/passport/`) не зависит от torch: читает строку краш-теста и `shield_calibration.json`. Вердикт — детерминированные правила в `report.decide()` (оценка ≥ 7 → разрешено; < 7 и щит совместим → с условиями; иначе нет). Паспорт замораживается при выдаче (`report_json`). PDF — fpdf2 + DejaVu Sans из `app/passport/fonts/` (кириллица и узбекская латиница); тексты PDF в `app/passport/i18n.py`.
- Frontend лежит в `by_billy/frontend/` (Next.js 16, второй разработчик), а не в `frontend/`. Подключён к реальному API: типы в `src/lib/types.ts` сверены с `docs/API.md`. Mock-данные включаются только явно через `NEXT_PUBLIC_USE_MOCK=1`; при смене типов обновлять и моки, иначе `npm run build` упадёт. Все строки UI — `src/lib/dictionary.ts` (uz/ru/en).
- Тепловая карта детектива во фронтенде не показывается: она построена по центральному квадрату 224×224 и на тестах попадает на подделку лишь в 4,8% случаев.
- Автоматизация (`app/automation/`): наблюдатель папок `data/watch/scanner` (автопечать шлюзом `Shlyuz-Auto` → копия в `incoming`) и `data/watch/incoming` (автопроверка → «Входящие» врача, сортировка danger/warning/ok), прогрев ИИ при старте, публичная QR-проверка `/check/{token}` (токен в таблице `public_checks`, не в реестре). В тестах наблюдатель и прогрев выключены (conftest), тесты зовут `watcher.run_once()`.
- Печать через сайт идёт через серверный роут Next.js с `MEDSEAL_DEVICE_TOKEN` в `.env.local` (создать: `python -m scripts.create_demo_device`).
- **Блокчейн-якорение** (`docs/BLOCKCHAIN.md` §7 — чем реализация отличается от плана): контракт в `contracts/` (Hardhat 2), бэкенд в `app/anchor/` (`chain.py` — web3-клиент и `MemoryChain` для тестов, `service.py` — батчи и проверка), дерево с доменами в `app/seal/merkle.py`. Выключено, пока в `backend/.env` нет `RPC_URL`/`CONTRACT_ADDRESS`/`ANCHOR_PRIVATE_KEY` — тогда `blockchain: null` в `/verify`. Расхождение с цепочкой → `forged`/`blockchain_mismatch`. Тесты никогда не ходят в настоящую сеть (conftest), фикстура `chain` подставляет `MemoryChain`. `config.py` читает `backend/.env` через python-dotenv. При старте `resync_local_chain` забывает батчи, которых нет в перезапущенном Hardhat-узле (только chain id 31337), и печати якорятся заново.
- **Безопасность (`docs/SECURITY.md`, раздел «As implemented»):** журнал аудита `audit_log` (`app/audit.py`, `GET /api/audit` для админа, только добавление), заголовки и лимит POST 120/мин на IP (`app/security.py`, в тестах лимит выключен), лимит 64 Мпикс до декодирования (`imaging.ImageTooLarge` → 413). Индекс «угроза → тест» — `tests/test_threats.py::THREAT_TESTS`, новый ✅ в SECURITY.md без теста роняет `test_every_threat_has_a_test`.
- Все документы — в `docs/` (`SPEC.md`, `ARCHITECTURE.md`, `API.md`, `TASKS.md`, `DEMO.md`, `BLOCKCHAIN.md`, `SECURITY.md`); в корне их копий нет.
- `reference/medseal_poc.py` — эталонный PoC печати (исходный архив `muhr.zip` удалён: остальное дублировало файлы в корне).
- **Аудит-ремедиация (ветка `fix/audit-2026-09`, см. `AUDIT_REMEDIATION_STATUS.md` за точным статусом на конкретный коммит):**
  - **Подпись v2 и сертификаты устройств (CRY-01/CRY-02):** новые печати подписываются каноническим v2-заголовком (`uid`, `device_id`, `created_at`, `meta_hash`, `patient_ref` — редактирование любого из них без ключа теперь сразу даёт `bad_signature`, а не только рассинхронизацию цепочки). Старые (`sig_version=1`) записи по-прежнему проверяются старым сообщением `root + meta_hash + uid` — формат тайлов/Меркла (`GOLDEN_ROOT`) не менялся и не может меняться. Корневой ключ (`scripts/create_root_key.py`) подписывает сертификат каждого устройства; запись без действительного сертификата — `forged`/`untrusted_device`. `MEDSEAL_REQUIRE_DEVICE_CERT=0` — режим миграции старых БД (предупреждение `device_not_certified` вместо отказа).
  - **Внешние якоря реестра (CRY-03):** после каждой печати в `MEDSEAL_ANCHOR_PATH` (`backend/anchors/anchors.jsonl`, в .gitignore) дописывается fsync'нутая, подписанная корнем строка `{n, head_hash, at, sig}`. `/ledger/check` проверяет и её тоже (`anchors_checked`, `anchor_mismatch`) — полная переписанная-и-пересчитанная цепочка внутри одной БД теперь обнаруживается.
  - **Восстановление печати по содержимому (P1-03):** если `uid` отсутствует/не найден, `verify/recovery.py` ищет кандидатов по перцептивному хешу (`dhash_hex`, не входит в `record_bytes()`) и подтверждает совпадением ≥50% тайлов. Печать без ID, производная от уже запечатанного снимка, отклоняется (`409`) при попытке запечатать заново.
  - **Привязка пациента (CRY-01):** `patient_ref = HMAC-SHA256(MEDSEAL_PATIENT_SALT, PatientID)` в подписи; расхождение при проверке — `tampered`/`patient_mismatch`, даже если пиксели не тронуты.
  - **Безопасность API (Фаза 2):** `GET /seal/{id}/file` и `GET /seals` теперь требуют токен устройства или админский; краш-тест работает на одном выделенном воркере (`ThreadPoolExecutor(max_workers=1)`), второй запрос во время выполнения — `409`; загрузка/печать/проверка идут через `run_in_threadpool`, `detective.check`/`shield.check` защищены `threading.Lock`; `ledger.append` — под процесс-локальным локом с одной повторной попыткой при `IntegrityError`; `MEDSEAL_MAX_PIXELS` (по умолчанию 64 000 000) проверяется по заголовку до декодирования пикселей.
  - **Снимки/DICOM (Фаза 3):** превью, щит и детектив видят `imaging.display_pixels()` (Modality LUT, VOI LUT, инверсия `MONOCHROME1`) — печать и `changed_tiles` всегда хешируют «сырой» массив. Деидентификация рекурсивно удаляет все элементы VR `PN` и расширенный список тегов, но **сохраняет все UID** (иначе печать сломается) — осознанное отклонение от DICOM PS3.15. `META_TAGS_V2` подписывает больше полей, включая оверлеи (группы `0x60xx`); ИИ не запускается вне `CR`/`DX` (`ai_note: "not_applicable"`).
  - **Честность паспорта (Фаза 5):** правило `shield.compatible` использует точечные оценки (порог 90%/2%), но паспорт и PDF показывают и 95%-й доверительный интервал (Клоппер–Пирсон), и `adaptive_attack_tested: false` — граница по интервалам сознательно не применяется при текущем размере калибровки (см. `ARCHITECTURE.md`). `allowed` недостижим без непустого `clinical_validation`; без него потолок — `allowed_with_conditions` + условие `clinical_validation_required`.

## Что делает продукт

1. **Печать (Seal)** — подписывает снимок в момент съёмки: тайлы → SHA-256 → корень Меркла → подпись Ed25519 → append-only реестр.
2. **Проверка (Verify)** — проверяет снимок до того, как его увидит врач/ИИ: подлинный / изменён (с точностью до тайла) / не подписан / поддельная запись.
3. **ИИ-детектив** — для неподписанных снимков: CNN (ResNet18) оценивает вероятность подделки и показывает тепловую карту (Grad-CAM).
4. **Краш-тест** — атакует медицинскую модель (FGSM/PGD) и выставляет оценку устойчивости 0–10.
5. **ИИ-щит** — обнаруживает состязательный шум до того, как снимок попадёт в диагностическую модель (feature squeezing).
6. **Паспорт модели** — одностраничный отчёт по модели (устойчивость, статус защиты, вердикт) с экспортом в PDF.

Подробности в `docs/`: `SPEC.md` (страницы и критерии приёмки), `ARCHITECTURE.md` (алгоритмы и схема БД), `API.md` (контракты эндпоинтов), `TASKS.md` (план на 3 дня и роли), `DEMO.md` (сценарий демо и ответы жюри).

## Стек

- **Backend:** Python 3.11+, FastAPI, pydicom, numpy, cryptography (Ed25519), Pillow, OpenCV, SQLite (SQLAlchemy)
- **AI:** PyTorch (достаточно CPU), torchxrayvision (предобученная DenseNet для рентгена грудной клетки), torchvision
- **Frontend:** Next.js (App Router) + TypeScript + Tailwind
- **Тесты:** pytest (backend), минимальный smoke-тест на Playwright (frontend, опционально)

## Целевая структура

```
backend/
  app/
    main.py            # FastAPI, роутеры, префикс /api
    seal/              # хеширование, Меркл, подпись, реестр (единственное место, где есть приватные ключи)
    verify/            # проверка + превью с красными рамками на изменённых тайлах
    ai/
      model.py         # загрузка torchxrayvision + predict()
      attacks.py       # FGSM / PGD
      shield.py        # детектор feature squeezing
      detective.py     # CNN для поиска подделок + Grad-CAM
    passport/          # сборка отчёта + экспорт PDF
    db.py, models.py   # таблицы SQLite
  keys/                # приватные ключи демо-устройств (в .gitignore)
  tests/
  scripts/             # подготовка данных, make_fakes.py, обучение детектива, калибровка щита
frontend/
  app/(pages)/seal, verify, crash-test, passport/[id], dashboard
data/                  # только публичные/синтетические снимки (в .gitignore)
reference/medseal_poc.py
```

## Команды

```bash
# backend (venv в backend/.venv, Python 3.14)
cd backend && python3 -m venv .venv && .venv/bin/pip install -r requirements-dev.txt   # requirements.txt = только рантайм
export MEDSEAL_ADMIN_TOKEN=dev-admin-token   # без него POST /devices, /revoke, /crash-test, /passport всегда 401
.venv/bin/uvicorn app.main:app --reload --port 8000   # Swagger: http://localhost:8000/docs
.venv/bin/pytest -m "not ai"   # быстрый гейт
.venv/bin/pytest               # полный набор; ИИ-тесты без torch — SKIPPED, не PASSED
.venv/bin/pytest tests/test_seal_core.py::test_one_pixel_change   # один тест
.venv/bin/python -m scripts.demo_smoke   # сквозной smoke-тест на временных БД/ключах/хранилище/якорях
# пути БД/ключей/хранилища переопределяются через MEDSEAL_DB_URL, MEDSEAL_KEYS_DIR, MEDSEAL_STORAGE_DIR

# первый запуск: корневой ключ → устройство с сертификатом (в этом порядке, один раз)
.venv/bin/python -m scripts.create_root_key      # backend/keys/root.{pem,pub} — не перезаписывает существующий
.venv/bin/python -m scripts.create_demo_device   # печатает токен устройства, вставить в frontend/.env.local
# миграция БД с печатями до CRY-02 (устройства без сертификата): создать root-ключ выше, затем
export MEDSEAL_ADMIN_TOKEN=dev-admin-token
.venv/bin/python -m scripts.certify_devices --authorization "Bearer $MEDSEAL_ADMIN_TOKEN"

# AI (torch CPU; работает на 3.14). Веса DenseNet кешируются в ~/.torchxrayvision
.venv/bin/pip install -r requirements-ai.txt --extra-index-url https://download.pytorch.org/whl/cpu
.venv/bin/python -m scripts.fetch_samples          # публичные рентгены в data/samples + веса (нужен интернет один раз)
.venv/bin/python -m scripts.attack_demo ../data/samples/00000001_000.png --eps 2 --method pgd   # до/после в data/demo; eps 2 — щит ловит с запасом
.venv/bin/python -m scripts.fetch_dataset          # NIH (data/nih) + Kermany (data/xray), нужен pyarrow
.venv/bin/python -m scripts.calibrate_shield       # порог щита -> app/ai/shield_calibration.json (~5 мин)
.venv/bin/python -m scripts.make_fakes             # демо-подделки для детектива -> data/demo/fakes (нужны веса детектива)
.venv/bin/python -m scripts.tamper_demo ~/Downloads/x.png   # узел на ПОДПИСАННОМ PNG/DICOM с сохранением medseal_uid/SOPInstanceUID -> x_tampered.png|.dcm (шаг 2 демо)
.venv/bin/pytest -m "not ai"                        # быстрые тесты без модели; ИИ-тесты сами пропускаются без весов/снимков
# MEDSEAL_AI=0 выключает щит/детектива в /verify (в тестах выключены по умолчанию, ИИ-тесты включают сами)
# скрипты запускать из backend/ через -m (им нужен пакет app)

# frontend (by_billy/frontend)
cd by_billy/frontend && npm install && cp .env.example .env.local && npm run dev   # http://localhost:3000
# .env.local: MEDSEAL_DEVICE_TOKEN (из create_demo_device), MEDSEAL_ADMIN_TOKEN (= MEDSEAL_ADMIN_TOKEN
# на бэкенде), MEDSEAL_GATEWAY_USER/PASSWORD (Basic Auth перед /seal и его API-роутами — без них 503)
npm run build && npm run lint                       # проверка типов и линтер
# доступ с других устройств в Wi-Fi: backend с --host 0.0.0.0, .env.local остаётся localhost:8000 —
# api.ts сам подставляет хост, с которого открыт сайт; CORS пускает любые частные IP:3000; после смены сети перезапустить npm run dev

# ДЕМО одной командой (вместо uvicorn): локальный блокчейн + контракт + backend, якорение каждые 15 с
./demo.sh                                                 # Ctrl+C гасит всё; порт: MEDSEAL_PORT

# автопроверка перед коммитом (один раз на клон): секреты + тесты изменённых частей; CI — .github/workflows/ci.yml
git config core.hooksPath .githooks

# блокчейн (contracts/, Node): локальная цепочка для офлайн-демо
cd contracts && npm install && npx hardhat test
npx hardhat node                                          # отдельный терминал, http://127.0.0.1:8545
npx hardhat run scripts/deploy.js --network localhost     # печатает CONTRACT_ADDRESS/CHAIN_ID -> backend/.env
npx hardhat run scripts/deploy.js --network sepolia && npx hardhat verify --network sepolia <адрес>
# backend: POST /api/anchors/run (admin) — якорить сразу; демо T4 (переписывает БД!):
.venv/bin/python -m scripts.rewrite_history_demo <seal_id> --image x_tampered.png

# эталонный PoC (печатает сценарии 0/A/B/C и тайминги, сохраняет medseal_check.png)
python reference/medseal_poc.py
```

## Архитектура: ключевые инварианты, разбросанные по документам

**Печать — это детерминированная криптография, без ИИ. Переносите `reference/medseal_poc.py`, не изобретайте заново.**

- Вход хеша тайла: `f"{uid}|{y}|{x}|{shape}|{dtype}"` (где `shape`/`dtype` — от самого тайла, краевые тайлы меньше) + сырые байты тайла (`np.ascontiguousarray(...).tobytes()`). Формат не менять без обновления тестов и повторной печати демо-данных.
- Размер тайла: 32×32 для снимков ≥ 256 px, 16×16 для меньших. Пиксели — в градациях серого с сохранением исходного dtype (int16 у КТ — не приводить к uint8).
- Меркл: листья сортируются по `(y, x)`, на нечётном уровне дублируется последний узел. **Формат тайлов/Меркла заморожен** (`GOLDEN_ROOT`) — новое всегда идёт в новые версионные поля, никогда внутрь `tile_hashes()`/`merkle_root()`.
- `uid` = DICOM `SOPInstanceUID`; для PNG генерируется UUID и записывается в tEXt-чанк `medseal_uid` (пиксели не меняются). Если `uid` отсутствует/не найден — восстановление по содержимому через `dhash_hex` + ≥50% совпадение тайлов (P1-03, `ARCHITECTURE.md` §1b), `dhash_hex` не входит в `record_bytes()`.
- Подпись: новые печати — v2 (`sig_version=2`, канонический заголовок с `uid`/`device_id`/`created_at`/`meta_hash`/`patient_ref`); старые (`sig_version=1`) — заморожённое сообщение `root + meta_hash + uid`, проверяются как раньше. Устройство должно иметь действительный сертификат от корневого ключа (`ARCHITECTURE.md` §1d), иначе `forged`/`untrusted_device` (или предупреждение `device_not_certified` при `MEDSEAL_REQUIRE_DEVICE_CERT=0`).
- Реестр — hash-chain: каждая запись хранит `prev_hash` и `entry_hash = sha256(prev_hash + record)`; дополнительно после каждой печати — подписанный корнем внешний якорь в `MEDSEAL_ANCHOR_PATH` (`ARCHITECTURE.md` §1c), защищающий от переписанной-и-пересчитанной цепочки внутри БД.
- `tests/test_seal_core.py::test_hash_format_is_frozen` фиксирует формат хеша эталонным значением, посчитанным функциями из `reference/medseal_poc.py`. Падает — значит сломан формат.
- Порядок статусов при проверке: нет записи по `uid` и по содержимому → `unsigned` (запустить детектива); сертификат устройства недействителен / подпись / целостность строки реестра / отзыв устройства не сходятся → `forged` (причина — в поле `reason`: `untrusted_device` / `bad_signature` / `ledger_entry_modified` / `device_revoked` / `unknown_device`); есть несовпавшие тайлы, изменены подписанные метаданные (`meta_hash`, `META_TAGS_V2`) или не совпал `patient_ref` → `tampered` (`reason`: `metadata_changed` / `seal_id_removed` / `patient_mismatch`); иначе `authentic` (возможно с `warning`: `device_revoked_later` / `seal_id_missing` / `device_not_certified`).
- Приватные ключи не покидают модуль `seal/`, никогда не логируются и не возвращаются API. Публичные ключи и `cert_sig_hex` — в таблице `devices`. Корневой ключ (`MEDSEAL_ROOT_KEY_PATH`, по умолчанию `backend/keys/root.pem`) подписывает и сертификаты устройств, и якоря реестра, и паспорта — верификатору достаточно `root.pub`.
- Новые переменные окружения бэкенда (все опциональны, см. `README.md` за полным списком с описаниями): `MEDSEAL_PATIENT_SALT`, `MEDSEAL_ROOT_KEY_PATH`/`MEDSEAL_ROOT_PUBKEY_PATH`, `MEDSEAL_REQUIRE_DEVICE_CERT`, `MEDSEAL_ANCHOR_PATH`, `MEDSEAL_MAX_PIXELS`.

**ИИ-модули:**

- Модель: `xrv.models.DenseNet(weights="densenet121-res224-all")`, вход `[1,1,224,224]`, нормализация как `xrv.datasets.normalize(img, 255)` (диапазон [-1024, 1024]; сама функция принимает только numpy, в `app/ai/model.py` формула на тензоре). Для демо — класс «Pneumonia». Выходы откалиброваны `op_threshs`, поэтому порог «болен» = 0.5 для всех патологий.
- Атака сама выбирает направление: здоровый снимок толкает вверх через 0.5, больной — вниз.
- eps в атаках задаётся в пикселях 0–255 (`[0.5, 1, 2, 4]`) и умножается на `2048/255` для нормализованного пространства. PGD = 10 шагов с шагом `eps/4` и проекцией на eps-шар.
- Оценка устойчивости: `round(10 × (1 − flip_rate при eps=1), 1)` — формулу нужно объяснять в паспорте.
- Щит: `d = Σ |logit(orig) − logit(median3×3)|` по патологиям на картинке 224×224, которую видит модель (сырые логиты, не калиброванные оценки). Порог = 99-й перцентиль `d` на чистых взрослых снимках NIH, лежит в `app/ai/shield_calibration.json` (коммитится). После смены модели или предобработки — перекалибровать. Детский датасет Kermany для калибровки и краш-теста не годится: для модели это чужой домен.
- Данные: `data/nih/{normal,findings}` (NIH ChestX-ray14, основной набор), `data/xray/{normal,pneumonia}` (Kermany, для детектива).

**Целевые показатели:** печать/проверка < 50 мс на снимок; щит < 1 с; краш-тест на 50 снимках < 2 мин на CPU.

## Блокчейн-якорение и модель угроз

- `docs/BLOCKCHAIN.md` — якорение реестра в смарт-контракт `MedSealAnchor` (батч-корень Меркла из `entry_hash`, поле `blockchain` в `/verify`).
- `docs/SECURITY.md` — криптопримитивы, модель угроз T1–T12, честные ограничения, демо атак для жюри.

Правила:
- **Секреты — только в `.env`** (в .gitignore): `MEDSEAL_ADMIN_TOKEN`, `ANCHOR_PRIVATE_KEY`, `RPC_URL` и т. п. Не хардкодить, не логировать, не возвращать из API, не класть в `NEXT_PUBLIC_*`.
- **Меркл с разделением доменов:** `leaf = sha256(0x00 || data)`, `node = sha256(0x01 || left || right)`. Новые деревья (батчи якорения) — сразу так. Дерево тайлов переводится только через версию формата в записи печати (старые печати проверяются по старому правилу), с новым эталоном в `test_hash_format_is_frozen` — формат v1 не ломать.
- **Тест на каждую угрозу:** каждая строка T1–T12 из `docs/SECURITY.md` с ✅ имеет pytest, который воспроизводит атаку и проверяет, что она поймана. Новая защита — вместе с тестом.

## Правила

- **Данные:** только публичные датасеты и синтетика. Никогда не коммитить реальные данные пациентов. При загрузке DICOM удалять теги пациента (PatientName, PatientID, BirthDate…) до сохранения чего-либо.
- **Честность в UI:** печать даёт точный ответ, детектив и щит — вероятность. Всегда подписывать по-разному («Tasdiqlangan» vs «Ehtimollik 87%»).
- **ИИ не решает сам:** каждый вердикт ИИ в UI сопровождается пометкой, что окончательное решение за врачом (в API — поле `note`).
- **Язык UI:** узбекский (латиница) по умолчанию, русский — переключателем. Все строки — в одном файле-словаре.
- **Приоритет хакатона:** работающее от начала до конца демо важнее новых фич. Перед добавлением чего-либо убедиться, что сценарий из `docs/DEMO.md` по-прежнему проходит. В конце каждого дня демо должно работать, пусть и с заглушками.
- **Страж демо:** `tests/test_demo_flow.py` проходит шаги 1, 2 и 3b из `docs/DEMO.md` настоящими скриптами и сверяет, что у каждой причины `forged` есть текст в `dictionary.ts` (иначе страница проверки падает). Новая причина в API — сразу добавить в `FORGED_REASONS` и в словарь.
- **Обязательные тесты:** round-trip печать/проверка, обнаружение изменения 1 пикселя, отклонение подделанного реестра (сценарии B и C из PoC), атака меняет предсказание, щит помечает атакованные снимки.
