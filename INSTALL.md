# Установка СОС · Installing SOS

**По-русски:** полная инструкция — [docs/ru/install.md](docs/ru/install.md).
**English:** the full guide is [docs/guides/install.md](docs/guides/install.md).

СОС в стадии пре-альфы: релиза ещё нет, но каждая сборка из `main` загружается в виртуальной
машине в CI, и её можно попробовать. SOS is pre-alpha: there is no release yet, but every build
from `main` is boot-tested in CI and can be tried.

## Быстрый путь: Windows + VirtualBox

1. **Скачай образ:** [sos-26.10-amd64.iso](https://github.com/svoya-os/sos/releases/download/test/sos-26.10-amd64.iso), около 1,7 ГБ, один файл, без регистрации.
   Это [тестовая сборка](https://github.com/svoya-os/sos/releases/tag/test); когда выйдет релиз, он будет на [Releases](https://github.com/svoya-os/sos/releases).
   Видеокарта NVIDIA, а интернета при установке не будет? Там же лежит образ с драйверами
   `sos-26.10-amd64-nvidia.iso` (частями, [как склеить](docs/ru/install.md#образ-с-nvidia-лежит-частями)).
2. **VirtualBox:** Создать → ISO, *Linux / Ubuntu (64-bit)*, «Пропустить автоматическую
   установку»; 8 ГБ памяти, 4 ядра, «Включить EFI»; диск 64 ГБ. Потом Настроить → Дисплей:
   *VMSVGA*, 128 МБ, 3D-ускорение **выключено** (в VirtualBox СОС рисует процессором). Запусти.
3. **Живая сессия** откроется сама. Пробуй что угодно — после перезагрузки всё сбросится.
   Джексон предложит кнопку **«Установить СОС»**, когда захочешь поставить систему на диск.

Флешка: [Rufus](https://rufus.ie) (режим *DD-образа*) или [balenaEtcher](https://etcher.balena.io).
Чёрный экран — пункт меню **safe graphics · безопасная графика**.

## Quick path: Windows + VirtualBox

1. **Download the image:** [sos-26.10-amd64.iso](https://github.com/svoya-os/sos/releases/download/test/sos-26.10-amd64.iso), about 1.7 GB, one file, no account
   needed. It is the [test build](https://github.com/svoya-os/sos/releases/tag/test); releases will be on [Releases](https://github.com/svoya-os/sos/releases). An NVIDIA card
   and no internet during the install? The same page has `sos-26.10-amd64-nvidia.iso` with the
   drivers (in parts, [how to join them](docs/guides/install.md#the-nvidia-image-comes-in-parts)).
2. **VirtualBox:** New → the ISO, *Linux / Ubuntu (64-bit)*, *Skip Unattended Installation*;
   8 GB of memory, 4 CPUs, *Enable EFI*; a 64 GB disk. Then Settings → Display: *VMSVGA*,
   128 MB, 3D acceleration **off** (in VirtualBox SOS draws on the CPU). Start it.
3. **The live session** opens by itself. Try anything: a reboot resets it. Jackson offers an
   **«Install SOS»** button when you want it on a disk.

USB stick: [Rufus](https://rufus.ie) (*DD image* mode) or [balenaEtcher](https://etcher.balena.io).
Black screen: pick **safe graphics** in the boot menu.

Linux and macOS, Hyper-V, QEMU, dual boot and troubleshooting are in the full guides above.
Building the ISO yourself: [docs/guides/build-from-source.md](docs/guides/build-from-source.md).
