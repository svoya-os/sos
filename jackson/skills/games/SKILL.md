---
name: games
description: Игры в СОС: Steam и Proton, Minecraft, Epic и GOG, геймпады, GameMode и MangoHud, что делать, если игра тормозит или не запускается.
aliases: steam, стим, proton, протон, майнкрафт, minecraft, геймпад, игр
---
## Поставить
- Steam: `sos установить steam`. Это модуль «Игры»: Steam, GameMode, MangoHud, gamescope, 32-битные драйверы (и для NVIDIA), правила для геймпадов. Спросит пароль; клиент Steam скачается у Valve при первом запуске.
- Minecraft: `sos установить prism` (Prism Launcher; вход через аккаунт Microsoft, саму игру покупают у Microsoft).
- Epic Games, GOG, Amazon: `sos установить heroic`. Всё в одном месте: `sos установить lutris`.
- Proton-GE и свежий Wine: `sos установить protonplus`. Эмуляторы приставок: `sos установить retroarch`.
- Discord, который показывает экран со звуком в Wayland: `sos установить vesktop`.

## Windows-игры в Steam
Steam → Настройки → Совместимость → «Включить Steam Play для всех остальных продуктов».
Не запускается: свойства игры → Совместимость → другая версия Proton (Experimental или GE-Proton из ProtonPlus).
Проверить игру заранее: protondb.com. Игры с античитом на уровне ядра (часть онлайн-шутеров) на Linux не пускают: это решает разработчик игры, не система.

## Параметры запуска (свойства игры → Параметры запуска)
- `gamemoderun %command%`: GameMode, процессор и видеокарта в режиме производительности.
- `mangohud %command%`: FPS, температура и загрузка поверх игры (правый Shift+F12 — показать или скрыть).
- Вместе: `gamemoderun mangohud %command%`.
- Масштаб и лимит кадров через gamescope: `gamescope -W 2560 -H 1440 -r 144 -f -- %command%`.

## Что СОС делает сама
- Игры (steam_app_*, *.exe из Wine и Proton, Minecraft, RetroArch) открываются в своём размере, без лишней рамки, и в режиме плитки тоже.
- Пока игра во весь экран, экран не гаснет и не блокируется: геймпад не считается клавиатурой.
- VRR (FreeSync, G-Sync Compatible) включается для окон во весь экран.

## Если тормозит или не запускается
- `sos видеокарта`: драйвер и что с ним. На NVIDIA нужен модуль: `sos установить nvidia`.
- Меньше задержка ценой разрывов кадра, для одной игры, строкой в `~/.config/hypr/user.conf`:
  `windowrule = immediate on, match:class ^(steam_app_ID)$` (ID — номер игры в Steam, игра во весь экран).
- Alt+Shift в игре переключает раскладку: можно переключать Caps Lock, строкой в `~/.config/hypr/user.conf`: `input { kb_options = grp:caps_toggle }`.
- Ошибки Steam видно, если запустить `steam` из терминала (Super+Enter).

Отвечай по делу: что нажать или какую команду выполнить, без общих слов про Linux.
