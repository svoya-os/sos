# SOS — Svoya Operating System (présentation courte)

> SOS est en pré-alpha. Cette page résume l'essentiel ; la documentation complète existe en
> [anglais](../../README.md#english) et en [russe](../../README.md#по-русски). Pour l'instant,
> l'interface et l'assistant parlent anglais et russe.

**SOS** (« СОС », *Svoya Operating System*, « le système d'exploitation à soi ») est une
distribution Linux libre pour travailler avec l'IA. Dessous tourne Ubuntu 26.04 LTS, comme un
moteur invisible ; tout ce que vous voyez et touchez est à nous : le bureau Svoya Shell,
l'assistant Jackson et la commande `sos`.

## Ce qu'il y a dedans

- **Carte graphique installée et vérifiée.** Pilotes signés et GPU Doctor (`sos gpu`), qui
  contrôle pilote ↔ CUDA ↔ PyTorch, Secure Boot, la mise en veille et l'accès au GPU depuis les
  conteneurs ; `sos fix` applique les corrections sûres.
- **Jackson, un assistant qui demande d'abord.** Il utilise des modèles locaux ou dans le cloud,
  lance des outils et d'autres agents dans des bacs à sable, montre exactement ce qu'il va faire
  avant toute action risquée, tient un journal infalsifiable et sait annuler ce qu'il a fait.
  On l'appelle avec `Super+J` ; avec le module vocal, maintenez `Super+J` et parlez (russe ou
  anglais, tout sur votre ordinateur).
- **Les outils d'IA en modules.** Rien n'est imposé : `sos install comfyui` et les autres, un seul
  magasin de modèles `/srv/ai` et, avant chaque téléchargement, la vérification que le modèle tient
  et que sa licence permet votre usage.
- **Un bureau à soi.** Les raccourcis de Windows fonctionnent (`Win`, `Win+Tab`, `Alt+Tab`,
  `Win+D`, `Win+flèches`, `Alt+F4`), avec l'historique du presse-papiers, les émojis, le texte de
  l'écran, la pipette, une calculatrice dans le lanceur, le mode jeu et un écran plus chaud le soir.
- **Tout est réversible.** Des instantanés Btrfs avant chaque mise à jour, changement de module
  et action de Jackson ; `Super+Z` ou `sos undo` annule le dernier changement.

La promesse : pas de publicité, pas de compte, pas de télémétrie ; l'IA ne démarre jamais seule ;
local par défaut.

## L'essayer dans une machine virtuelle (environ 15 minutes)

1. Téléchargez une version de test : [Actions → ISO](https://github.com/svoya-os/sos/actions/workflows/iso.yml)
   → la première exécution avec une coche verte → *Artifacts* → **sos-iso** (compte GitHub requis).
2. Décompressez et assemblez les parties. Windows (PowerShell) :
   `cmd /c copy /b sos-26.10-amd64.iso.part00 + sos-26.10-amd64.iso.part01 sos-26.10-amd64.iso` ;
   Linux/macOS : `cat sos-26.10-amd64.iso.part* > sos-26.10-amd64.iso`. Vérifiez avec `SHA256SUMS`.
3. VirtualBox : *Linux / Ubuntu (64-bit)*, 8 Go de mémoire, 4 processeurs, *Activer EFI*,
   affichage *VMSVGA* sans 3D, démarrez sur l'ISO.
4. Vous êtes sur le bureau de la session live. `Super+K` montre tous les raccourcis ;
   **« Install SOS »** dans l'accueil de Jackson installe le système sur un disque.

## Matériel

PC 64 bits (amd64) avec UEFI. NVIDIA RTX 20–50 : cible principale ; GTX 900/1000 : pilote
historique ; AMD Radeon RX 7000/9000 et Ryzen AI Max : pris en charge ; Intel Arc : l'essentiel ;
sans carte graphique tout fonctionne, mais l'IA locale se limite aux petits modèles.

## Pour aller plus loin

[Guide d'installation](../guides/install.md) · [Premiers pas](../guides/first-steps.md) ·
[En venant de Windows](../guides/from-windows.md) · [FAQ](../guides/faq.md) (en anglais) ·
[Signaler un bug](https://github.com/svoya-os/sos/issues) · Licence : Apache-2.0.
