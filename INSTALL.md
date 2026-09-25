# Установка СОС · Installing SOS

**По-русски:** полная инструкция — [docs/ru/install.md](docs/ru/install.md).
**English:** the full guide is [docs/guides/install.md](docs/guides/install.md).

СОС в стадии пре-альфы: релиза ещё нет, но каждая сборка из `main` загружается в виртуальной
машине в CI, и её можно попробовать. SOS is pre-alpha: there is no release yet, but every build
from `main` is boot-tested in CI and can be tried.

## Быстрый путь: Windows + VirtualBox

1. **Скачай образ.** [Actions → ISO](https://github.com/svoya-os/sos/actions/workflows/iso.yml) →
   верхний запуск с зелёной галочкой → *Artifacts* → **sos-iso** (нужен аккаунт GitHub). Когда
   выйдет релиз — [Releases](https://github.com/svoya-os/sos/releases).
2. **Склей части** (PowerShell в папке с файлами):

   ```powershell
   cmd /c copy /b sos-26.10-amd64.iso.part00 + sos-26.10-amd64.iso.part01 sos-26.10-amd64.iso
   Get-FileHash sos-26.10-amd64.iso -Algorithm SHA256    # сверь с SHA256SUMS
   ```

3. **VirtualBox:** Создать → ISO, *Linux / Ubuntu (64-bit)*, «Пропустить автоматическую
   установку»; 8 ГБ памяти, 4 ядра, «Включить EFI»; диск 64 ГБ. Потом Настроить → Дисплей:
   *VMSVGA*, 3D-ускорение. Запусти.
4. **Живая сессия** откроется сама. Пробуй что угодно — после перезагрузки всё сбросится.
   Джексон предложит кнопку **«Установить СОС»**, когда захочешь поставить систему на диск.

Флешка: [Rufus](https://rufus.ie) (режим *DD-образа*) или [balenaEtcher](https://etcher.balena.io).
Чёрный экран — пункт меню **safe graphics · безопасная графика**.

## Quick path: Windows + VirtualBox

1. **Download the image.** [Actions → ISO](https://github.com/svoya-os/sos/actions/workflows/iso.yml)
   → the top run with a green check → *Artifacts* → **sos-iso** (needs a GitHub account). Once
   released: [Releases](https://github.com/svoya-os/sos/releases).
2. **Join the parts** (PowerShell in the folder with the files):

   ```powershell
   cmd /c copy /b sos-26.10-amd64.iso.part00 + sos-26.10-amd64.iso.part01 sos-26.10-amd64.iso
   Get-FileHash sos-26.10-amd64.iso -Algorithm SHA256    # compare with SHA256SUMS
   ```

3. **VirtualBox:** New → the ISO, *Linux / Ubuntu (64-bit)*, *Skip Unattended Installation*;
   8 GB of memory, 4 CPUs, *Enable EFI*; a 64 GB disk. Then Settings → Display: *VMSVGA*,
   3D acceleration. Start it.
4. **The live session** opens by itself. Try anything: a reboot resets it. Jackson offers an
   **«Install SOS»** button when you want it on a disk.

USB stick: [Rufus](https://rufus.ie) (*DD image* mode) or [balenaEtcher](https://etcher.balena.io).
Black screen: pick **safe graphics** in the boot menu.

Linux and macOS, Hyper-V, QEMU, dual boot and troubleshooting are in the full guides above.
Building the ISO yourself: [docs/guides/build-from-source.md](docs/guides/build-from-source.md).
