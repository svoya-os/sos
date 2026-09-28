#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Release notes for the download page: which image to take, and how.

    scripts/release/notes.py DIR SHA test|release [TAG] > DIR/NOTES.md

DIR holds what the ISO workflow made: *.iso (whole) and *.iso.partNN, SHA256SUMS and the *.iso.json
build info (size, variant). The standard image is one file; the one with the NVIDIA drivers comes
in parts (GitHub keeps files under 2 GiB) and sos-join.bat / sos-join.sh put it together.
"""
from __future__ import annotations

import json
import pathlib
import sys

INSTALL_RU = "https://github.com/svoya-os/sos/blob/main/docs/ru/install.md"
INSTALL_EN = "https://github.com/svoya-os/sos/blob/main/docs/guides/install.md"


def gb(n: int, ru: bool) -> str:
    # binary gigabytes, as Windows Explorer and the file managers show the downloaded file
    v = f"{n / 2**30:.1f}"
    return (v.replace(".", ",") + " ГБ") if ru else (v + " GB")


def images(d: pathlib.Path) -> list[dict]:
    out = []
    for f in sorted(d.glob("*.iso.json")):
        info = json.loads(f.read_text(encoding="utf-8"))
        name = info["iso"]
        parts = sorted(p.name for p in d.glob(f"{name}.part*"))
        out.append({"name": name, "bytes": int(info.get("isoBytes") or 0), "parts": parts,
                    "nvidia": info.get("variant") == "nvidia"})
    # the standard image first: it is what most people need
    return sorted(out, key=lambda i: i["nvidia"])


def fetch(img: dict, ru: bool) -> str:
    """How to get an image that comes in parts; nothing for one file."""
    if not img["parts"]:
        return ""
    files = ", ".join(f"`{p}`" for p in img["parts"])
    if ru:
        return (f" GitHub не принимает файлы больше 2 ГБ, поэтому образ лежит частями: скачай в одну папку {files}, "
                "`SHA256SUMS` и `sos-join.bat` с `sos-join.ps1` (Windows) или `sos-join.sh` (Linux, macOS) и запусти "
                "sos-join: он склеит образ и проверит его.")
    return (f" GitHub takes files under 2 GB, so it comes in parts: download {files}, `SHA256SUMS` and "
            "`sos-join.bat` with `sos-join.ps1` (Windows) or `sos-join.sh` (Linux, macOS) into one folder and run "
            "sos-join: it joins the image and checks it.")


def size(img: dict, ru: bool) -> str:
    one = ("один файл" if ru else "one file") if not img["parts"] else ("частями" if ru else "in parts")
    return f"{gb(img['bytes'], ru)}, {one}"


def notes(d: pathlib.Path, sha: str, kind: str, tag: str = "") -> str:
    imgs = images(d)
    if not imgs:
        raise SystemExit("notes.py: no *.iso.json in " + str(d))
    std = next((i for i in imgs if not i["nvidia"]), None)
    nv = next((i for i in imgs if i["nvidia"]), None)
    lines: list[str] = []
    if kind == "test":
        lines += [f"**Тестовая сборка СОС** (пре-альфа, коммит `{sha[:7]}`). Обновляется сама после каждой "
                  "сборки, которая загрузилась, установилась и прошла проверку ботами.", ""]
    else:
        lines += [f"**СОС {tag}**", ""]
    lines += ["### Какой образ скачать", ""]
    if std:
        lines.append(f"- **`{std['name']}`** ({size(std, True)}) подойдёт почти всем. С видеокартой NVIDIA "
                     f"и интернетом драйвер скачается при установке.{fetch(std, True)}")
    if nv:
        lines.append(f"- **`{nv['name']}`** ({size(nv, True)}): с драйверами NVIDIA, для установки без "
                     f"интернета.{fetch(nv, True)}")
    lines += ["", "Проверить образ: суммы в `SHA256SUMS`. Записать на флешку: [Rufus](https://rufus.ie) "
              "(режим DD), [balenaEtcher](https://etcher.balena.io) или Ventoy. Secure Boot выключать не нужно. "
              f"Подробно: [установка]({INSTALL_RU}).", "", "---", ""]
    if kind == "test":
        lines += [f"**SOS test build** (pre-alpha, commit `{sha[:7]}`). Replaced automatically by every build "
                  "that boots, installs and passes the bots.", ""]
    else:
        lines += [f"**SOS {tag}**", ""]
    lines += ["### Which image", ""]
    if std:
        lines.append(f"- **`{std['name']}`** ({size(std, False)}) suits almost everyone. With an NVIDIA card "
                     f"and internet, the driver is downloaded during the install.{fetch(std, False)}")
    if nv:
        lines.append(f"- **`{nv['name']}`** ({size(nv, False)}) carries the NVIDIA drivers, for installing "
                     f"without internet.{fetch(nv, False)}")
    lines += ["", "Checksums are in `SHA256SUMS`. Write the image to a USB stick with [Rufus](https://rufus.ie) "
              "(DD mode), [balenaEtcher](https://etcher.balena.io) or Ventoy; Secure Boot can stay on. "
              f"Details: [installing SOS]({INSTALL_EN}).", ""]
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    if len(argv) < 3 or argv[2] not in ("test", "release"):
        print(__doc__, file=sys.stderr)
        return 2
    sys.stdout.write(notes(pathlib.Path(argv[0]), argv[1], argv[2], argv[3] if len(argv) > 3 else ""))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
