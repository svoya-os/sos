# SOS — Svoya Operating System (presentación breve)

> SOS está en fase prealfa. Esta página resume lo esencial; la documentación completa está en
> [inglés](../../README.md#english) y en [ruso](../../README.md#по-русски). Por ahora la interfaz
> y el asistente hablan inglés y ruso.

**SOS** («СОС», *Svoya Operating System*, «el sistema operativo propio») es una distribución Linux
de código abierto para trabajar con IA. Debajo funciona Ubuntu 26.04 LTS como un motor invisible;
todo lo que ves y tocas es propio: el escritorio Svoya Shell, el asistente Jackson y la orden `sos`.

## Qué trae

- **Tarjeta gráfica configurada y comprobada.** Controladores firmados y GPU Doctor (`sos gpu`),
  que revisa controlador ↔ CUDA ↔ PyTorch, Secure Boot, suspensión y el acceso a la GPU desde
  contenedores; `sos fix` aplica los arreglos seguros.
- **Jackson, un asistente que pregunta primero.** Usa modelos locales o en la nube, ejecuta
  herramientas y otros agentes en entornos aislados, muestra exactamente qué va a hacer antes de
  cualquier paso arriesgado, lleva un registro a prueba de manipulaciones y puede deshacer lo que
  hizo. Se le llama con `Super+J`; con el módulo de voz mantienes `Super+J` pulsado y hablas
  (ruso o inglés, todo en tu equipo).
- **Las herramientas de IA como módulos.** Nada es obligatorio: `sos install comfyui` y demás, un
  único almacén de modelos `/srv/ai` y, antes de cada descarga, la comprobación de si el modelo
  cabe y qué permite su licencia.
- **Un escritorio propio.** Funcionan las teclas de Windows (`Win`, `Win+Tab`, `Alt+Tab`,
  `Win+D`, `Win+flechas`, `Alt+F4`), con historial del portapapeles, emojis, texto de la pantalla,
  cuentagotas de color, calculadora en el lanzador, modo juego y pantalla cálida por la noche.
- **Todo se puede deshacer.** Instantáneas Btrfs antes de cada actualización, cambio de módulos y
  acción de Jackson; `Super+Z` o `sos undo` revierten el último cambio.

La promesa: sin anuncios, sin cuenta, sin telemetría; la IA nunca arranca sola; local por defecto.

## Probarlo en una máquina virtual (unos 15 minutos)

1. Descarga una compilación de prueba: [Actions → ISO](https://github.com/svoya-os/sos/actions/workflows/iso.yml)
   → la primera ejecución con marca verde → *Artifacts* → **sos-iso** (necesitas cuenta de GitHub).
2. Descomprime y une las partes. Windows (PowerShell):
   `cmd /c copy /b sos-26.10-amd64.iso.part00 + sos-26.10-amd64.iso.part01 sos-26.10-amd64.iso`;
   Linux/macOS: `cat sos-26.10-amd64.iso.part* > sos-26.10-amd64.iso`. Compruébalo con `SHA256SUMS`.
3. VirtualBox: *Linux / Ubuntu (64-bit)*, 8 GB de memoria, 4 CPU, *Habilitar EFI*, gráficos
   *VMSVGA* sin 3D, e iníciala con la ISO.
4. Estás en el escritorio de la sesión en vivo. `Super+K` muestra todos los atajos; **«Install
   SOS»** en el saludo de Jackson instala el sistema en un disco.

## Hardware

PC de 64 bits (amd64) con UEFI. NVIDIA RTX 20–50: objetivo principal; GTX 900/1000: controlador
heredado; AMD Radeon RX 7000/9000 y Ryzen AI Max: compatibles; Intel Arc: lo básico; sin tarjeta
gráfica todo funciona, pero la IA local solo con modelos pequeños.

## Más

[Guía de instalación](../guides/install.md) · [Primeros pasos](../guides/first-steps.md) ·
[Si vienes de Windows](../guides/from-windows.md) · [Preguntas frecuentes](../guides/faq.md)
(todo en inglés) · [Informar de un error](https://github.com/svoya-os/sos/issues) · Licencia: Apache-2.0.
