# SOS — Svoya Operating System (apresentação curta)

> O SOS está em pré-alfa. Esta página resume o essencial; a documentação completa está em
> [inglês](../../README.md#english) e em [russo](../../README.md#по-русски). Por enquanto a
> interface e o assistente falam inglês e russo.

**SOS** («СОС», *Svoya Operating System*, «o sistema operacional próprio») é uma distribuição Linux
de código aberto para trabalhar com IA. Por baixo roda o Ubuntu 26.04 LTS, como um motor invisível;
tudo o que você vê e toca é nosso: a área de trabalho Svoya Shell, o assistente Jackson e o
comando `sos`.

## O que vem nele

- **Placa de vídeo configurada e verificada.** Drivers assinados e o GPU Doctor (`sos gpu`), que
  confere driver ↔ CUDA ↔ PyTorch, Secure Boot, suspensão e o acesso à GPU a partir de
  contêineres; `sos fix` aplica as correções seguras.
- **Jackson, um assistente que pergunta antes.** Usa modelos locais ou na nuvem, executa
  ferramentas e outros agentes em sandboxes, mostra exatamente o que vai fazer antes de qualquer
  passo arriscado, mantém um registro à prova de adulteração e desfaz o que fez. Chame-o com
  `Super+J`; com o módulo de voz, segure `Super+J` e fale (russo ou inglês, tudo no seu computador).
- **Ferramentas de IA em módulos.** Nada é imposto: `sos install comfyui` e outros, um único
  repositório de modelos `/srv/ai` e, antes de cada download, a verificação se o modelo cabe e o
  que a licença permite.
- **Uma área de trabalho própria.** As teclas do Windows funcionam (`Win`, `Win+Tab`, `Alt+Tab`,
  `Win+D`, `Win+setas`, `Alt+F4`), com histórico da área de transferência, emojis, texto da tela,
  conta-gotas de cor, calculadora no lançador, modo jogo e tela mais quente à noite.
- **Tudo é reversível.** Snapshots Btrfs antes de cada atualização, mudança de módulo e ação do
  Jackson; `Super+Z` ou `sos undo` desfaz a última mudança.

A promessa: sem anúncios, sem conta, sem telemetria; a IA nunca inicia sozinha; local por padrão.

## Experimente numa máquina virtual (uns 15 minutos)

1. Baixe uma versão de teste: [Actions → ISO](https://github.com/svoya-os/sos/actions/workflows/iso.yml)
   → a primeira execução com o visto verde → *Artifacts* → **sos-iso** (precisa de conta no GitHub).
2. Descompacte e junte as partes. Windows (PowerShell):
   `cmd /c copy /b sos-26.10-amd64.iso.part00 + sos-26.10-amd64.iso.part01 sos-26.10-amd64.iso`;
   Linux/macOS: `cat sos-26.10-amd64.iso.part* > sos-26.10-amd64.iso`. Confira com `SHA256SUMS`.
3. VirtualBox: *Linux / Ubuntu (64-bit)*, 8 GB de memória, 4 CPUs, *Habilitar EFI*, vídeo
   *VMSVGA* sem 3D, inicie com a ISO.
4. Você está na área de trabalho da sessão live. `Super+K` mostra todos os atalhos;
   **«Install SOS»** na saudação do Jackson instala o sistema num disco.

## Hardware

PCs de 64 bits (amd64) com UEFI. NVIDIA RTX 20–50: alvo principal; GTX 900/1000: driver legado;
AMD Radeon RX 7000/9000 e Ryzen AI Max: suportadas; Intel Arc: o básico; sem placa de vídeo tudo
funciona, mas a IA local fica limitada a modelos pequenos.

## Mais

[Guia de instalação](../guides/install.md) · [Primeiros passos](../guides/first-steps.md) ·
[Vindo do Windows](../guides/from-windows.md) · [Perguntas frequentes](../guides/faq.md) (em
inglês) · [Relatar um problema](https://github.com/svoya-os/sos/issues) · Licença: Apache-2.0.
