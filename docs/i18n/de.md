# SOS — Svoya Operating System (Kurzvorstellung)

> SOS ist im Pre-Alpha-Stadium. Diese Seite fasst das Wichtigste zusammen; die vollständige
> Dokumentation gibt es auf [Englisch](../../README.md#english) und [Russisch](../../README.md#по-русски).
> Oberfläche und Assistent sprechen vorerst Englisch und Russisch.

**SOS** («СОС», *Svoya Operating System* — „das eigene Betriebssystem“) ist eine quelloffene
Linux-Distribution für die Arbeit mit KI. Darunter läuft Ubuntu 26.04 LTS als unsichtbarer Motor;
alles, was du siehst und anfasst, ist eigen: der Desktop Svoya Shell, der Assistent Jackson und der
Befehl `sos`.

## Was drin ist

- **Grafikkarte eingerichtet und geprüft.** Signierte Treiber, GPU Doctor (`sos gpu`) prüft
  Treiber ↔ CUDA ↔ PyTorch, Secure Boot, Standby und GPU-Zugriff aus Containern; `sos fix`
  wendet die sicheren Korrekturen an.
- **Jackson, ein Assistent, der zuerst fragt.** Er nutzt lokale oder Cloud-Modelle, startet
  Werkzeuge und andere Agenten in Sandboxen, zeigt vor jedem riskanten Schritt genau, was er tun
  wird, führt ein fälschungssicheres Protokoll und kann rückgängig machen, was er getan hat.
  `Super+J` ruft ihn; mit dem Sprachmodul hältst du `Super+J` gedrückt und sprichst einfach
  (Russisch oder Englisch, alles auf deinem Rechner).
- **KI-Werkzeuge als Module.** Nichts wird aufgezwungen: `sos install comfyui` und Co., ein
  gemeinsamer Modellspeicher `/srv/ai`, vor jedem Download die Prüfung, ob das Modell passt und
  was seine Lizenz erlaubt.
- **Ein eigener Desktop.** Die Tasten aus Windows funktionieren (`Win`, `Win+Tab`, `Alt+Tab`,
  `Win+D`, `Win+Pfeile`, `Alt+F4`), dazu Zwischenablage-Verlauf, Emoji, Text vom Bildschirm,
  Farbpipette, Rechner im Starter, Spielmodus und ein warmer Bildschirm am Abend.
- **Alles umkehrbar.** Btrfs-Snapshots vor jedem Update, jeder Moduländerung und jeder Aktion
  von Jackson; `Super+Z` oder `sos undo` macht die letzte Änderung rückgängig.

Das Versprechen: keine Werbung, kein Konto, keine Telemetrie; KI startet nie von selbst; lokal
als Standard.

## In einer virtuellen Maschine ausprobieren (etwa 15 Minuten)

1. Testbuild laden: [Actions → ISO](https://github.com/svoya-os/sos/actions/workflows/iso.yml) →
   oberster Lauf mit grünem Haken → *Artifacts* → **sos-iso** (GitHub-Konto nötig).
2. Entpacken und die Teile zusammenfügen. Windows (PowerShell):
   `cmd /c copy /b sos-26.10-amd64.iso.part00 + sos-26.10-amd64.iso.part01 sos-26.10-amd64.iso`;
   Linux/macOS: `cat sos-26.10-amd64.iso.part* > sos-26.10-amd64.iso`. Mit `SHA256SUMS` prüfen.
3. VirtualBox: *Linux / Ubuntu (64-bit)*, 8 GB Arbeitsspeicher, 4 CPUs, *EFI aktivieren*, Grafik
   *VMSVGA* ohne 3D, mit der ISO starten.
4. Du bist auf dem Desktop der Live-Sitzung. `Super+K` zeigt alle Tastenkürzel; **„Install SOS“**
   in Jacksons Begrüßung installiert das System auf eine Festplatte.

## Hardware

64-Bit-PCs (amd64) mit UEFI. NVIDIA RTX 20–50: Hauptziel; GTX 900/1000: Legacy-Treiber;
AMD Radeon RX 7000/9000 und Ryzen AI Max: unterstützt; Intel Arc: Grundfunktionen; ohne
Grafikkarte läuft alles, lokale KI dann nur mit kleinen Modellen.

## Mehr

[Installationsanleitung](../guides/install.md) · [Erste Schritte](../guides/first-steps.md) ·
[Umstieg von Windows](../guides/from-windows.md) · [FAQ](../guides/faq.md) (alles auf Englisch) ·
[Fehler melden](https://github.com/svoya-os/sos/issues) · Lizenz: Apache-2.0.
