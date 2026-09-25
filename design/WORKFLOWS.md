# SOS — Key workflows and the details that make them feel right

Each workflow lists: entry points → steps → states (empty · loading · error) → the small details → how to undo.
Companion to `design/DESIGN.md` (look) and `docs/ARCHITECTURE.md` (contracts).

## Global rules for every workflow

* **Every change is reversible** and says how: a toast «Готово · Отменить (Super+Z)», `sos undo`, `jackson undo`.
* **Nothing blocks the desktop.** Long work (downloads, installs, training) becomes a *job* in the bar with a meter;
  closing a window never cancels a job; a finished job sends one notification.
* **One primary action per surface**, always on `Enter`; `Esc` closes without side effects; `Tab` moves focus.
* **Three entry points for every setting**: GUI (control center / settings), command (`sos …`), Jackson (plain words).
  All three call the same `sos` command, so behavior and undo are identical.
* **Honest waiting**: a spinner only under 2 s; otherwise real progress (bytes, steps, ETA) in mono.
* **Errors say what happened, why, and the one fix** — with a button that runs it (after a snapshot).
* **Sounds are rare**: login, notification, Jackson listen/done/error. Never for routine clicks.

## 1. First start (fresh install)

GRUB (neutral, hidden unless Shift/Esc) → Plymouth «СИГНАЛ» (neutral) → greeter (autologin after install) →
POST (1.2 s, real hardware facts) → first-run wizard (≤ 7 steps, each skippable, choices apply live):

1. **Доступность** — larger text, high contrast, reduce motion, screen reader; also `Super+Alt+A` any time.
2. **Язык и клавиатура** — RU/EN/ET UI, layouts, switch keys (Alt+Shift default), test field.
3. **Оформление** — base theme (Графит · Бумага · Авто · Фосфор) + accent (8 swatches + «Свой…») + startup sound;
   live preview of the real desktop behind the wizard; «Использовать на экране входа» (on for the first user).
4. **Раскладка** — Clean (floating) · Classic (taskbar) · Hacker (tiling); animated thumbnails; `Super+T` hint.
5. **Профиль** — Новичок · Творец · ML-инженер · Строитель агентов · Хакер (+ «только офлайн»); apps with
   Obsidian pre-checked; shows disk it will take.
6. **Джексон** — meet him: character (Чёрт/Кот), quick look (skin, outfit = accent), name, humor; then his brain:
   GPU/RAM detected, ONE suggested local model that fits (fit bar, size, license, «Установить»), 2 alternatives,
   optional cloud keys (stored in the keyring), route (local/auto/cloud) from the profile.
7. **Приватность и первый снимок** — what never leaves the machine, the AI off switch, first snapshot, shortcut
   cheat sheet (Super+K), «Готово».

Details: the wizard never needs the network except for downloads the user starts; downloads continue after the
wizard closes (job in the bar); a failed download offers «Повторить» and a smaller model; everything chosen is in
Settings later. States: offline → model step shows «Скачаем, когда появится сеть» and queues the job.
Undo: every step's choice is independent and can be changed in Settings; «Сбросить мастер» re-opens it.

## 2. Change the look (theme, accent, Jackson)

Entry: control center (click the clock/status area) → «Оформление» · `sos theme …` · Jackson («сделай тёмную тему»,
«акцент фиолетовый», «стань котом») · Settings → Оформление / Джексон.
Steps: pick → everything cross-fades in 260 ms (bar, panels, windows, terminal, GTK/Qt apps, wallpaper signal,
mascot) → toast «Акцент: Сирень · Отменить».
Details: the swatch under the pointer previews on hover (no commit until click); «Свой…» opens a hex field with a
live contrast badge (AA ✓ / «подправили яркость для читаемости»); Auto shows today's switch times; the
mascot's outfit follows the accent unless the user pinned another color; the login screen updates only if
«на экране входа» is on (asks for the admin password once, via polkit).
Undo: `Super+Z`, the toast, or `sos undo`.

## 3. Ask Jackson

Entry: `Super+J` (tap = panel, hold = push-to-talk), `Super+Space` then `?`, `j …` in a terminal, a region
screenshot (`Super+Shift+S` → «Спросить Джексона»), selected text + `Super+J`.
Steps: route chip appears first (local/cloud + model, why) → streamed answer → tool rows with live state →
approval card when a T2+ action is needed (exact preview, «Разрешить один раз» · «Всегда в этом проекте» ·
«Отклонить») → footer: time · tokens · € · «данные не покидали компьютер» → done sound (quiet).
States: no model yet → one-click «Поставить модель» (from `sos models suggest`) or «Подключить облако»;
model busy (GPU full) → «Сейчас идёт обучение — ответить облаком или подождать?»; offline + cloud route →
falls back to local and says so.
Details: `Esc` stops generation but keeps the text; `Tab` refines (keeps context); the mascot mirrors state
(listening/thinking/talking/happy/error); the Morse mark in the bar lights up while he works; the panel remembers
its last scroll position for 5 minutes; every file Jackson touched is listed with «Показать» and «Отменить».
Undo: «Отменить» on the done card, `jackson undo`, `Super+Z`.

## 4. Get a model or a module

Entry: launcher («flux», «comfyui»), Jackson («поставь модель для видео»), `sos install …`, Settings → Модели /
Модули, the wizard.
Steps: fit check first (VRAM/RAM/disk bars, license for your region) → confirm (size, where it goes, what it
changes) → job in the bar with bytes/s and ETA → notification «Готово · Открыть в Студии».
States: doesn't fit → suggests a smaller quant or offload with honest speed; license excludes your region → blocked
with the reason; disk low → shows what can be freed (`sos models dedup`, old snapshots); network drops → resumes.
Details: shared model store, no duplicates; installing a module takes a snapshot first; uninstalling removes
everything it added (and says what stays: your projects, your models).
Undo: `sos undo`, `sos remove <thing>`.

## 5. Train or fine-tune

Entry: `sos new <name> --template llm-finetune`, then `sos run train.py`; or «Создай проект для файнтюна» to Jackson.
Steps: environment header (torch/CUDA/GPU) → job in the bar (progress, loss sparkline in the tooltip) → focus mode
«Обучение» (no sleep, no update reboots, notifications muted) → done notification with the final metric and
«Открыть трекинг».
States: CUDA mismatch → GPU Doctor explains and offers the right backend; OOM → suggests batch/quant/offload;
laptop on battery → warns before starting.
Details: checkpoints never go into snapshots; the job survives logging out (systemd user service); the bar meter
hides when idle.

## 6. Update the system

Entry: a quiet dot on the status area when updates exist (never a pop-up); control center → «Обновить»;
`sos update`.
Steps: snapshot «перед обновлением» → download → install → «Перезагрузить сейчас / вечером / потом»; never
during focus mode «Обучение» or «Презентация».
States: kernel/NVIDIA mismatch detected → holds the kernel and explains; failure → automatic rollback offer.
Details: security updates install quietly; everything else waits for the user; a changelog in plain words.
Undo: boot menu «Вчерашняя система», `sos undo`.

## 7. Something broke

Entry: `Super+Esc` (System Doctor), notification from a failed service, «почему не работает звук?» to Jackson.
Steps: checks run in ~2 s with live rows (ok/warn/fail) → each problem shows what/why/fix → «Починить» (snapshot
first) → re-check.
Details: a copyable report (`sos doctor --report`) without personal data; «Не помогло» opens a pre-filled issue.

## 8. Privacy and the AI switch

Entry: control center → «ИИ и приватность», `sos ai off`, Jackson «выключись».
Details: one switch stops Jackson, local model servers and every agent; the bar shows a small «ИИ выкл.»;
the cloud indicator (cyan dot) appears whenever anything leaves the machine, with a journal («сегодня: 3 запроса
в облако — открыть журнал»); spend today in €; nothing is uploaded without a visible reason.
