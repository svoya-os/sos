# SOS — Svoya Operating System (lühitutvustus)

> SOS on alles alfaeelses järgus. Siin on kõige olulisem; täielik dokumentatsioon on
> [inglise](../../README.md#english) ja [vene](../../README.md#по-русски) keeles. Seni räägivad
> kasutajaliides ja abiline inglise ja vene keelt.

**SOS** («СОС», *Svoya Operating System* — „oma operatsioonisüsteem“) on avatud lähtekoodiga
Linuxi distributsioon tehisintellektiga töötamiseks. Selle all töötab nähtamatu mootorina Ubuntu
26.04 LTS; kõik, mida näed ja puudutad, on meie oma: töölaud Svoya Shell, abiline Jackson ja käsk
`sos`.

## Mis seal sees on

- **Videokaart on seadistatud ja kontrollitud.** Allkirjastatud draiverid ja GPU Doctor
  (`sos gpu`), mis kontrollib ahelat draiver ↔ CUDA ↔ PyTorch, Secure Booti, unerežiimi ja GPU
  kasutamist konteineritest; `sos fix` teeb ohutud parandused.
- **Jackson, abiline, kes küsib enne.** Kasutab kohalikke või pilvemudeleid, käivitab tööriistu
  ja teisi agente liivakastis, näitab enne iga riskantset sammu täpselt, mida ta teeb, peab
  logi, mida ei saa märkamatult muuta, ja oskab oma tegevusi tagasi võtta. Kutsu teda klahviga
  `Super+J`; häälemooduliga hoia `Super+J` all ja lihtsalt räägi (vene või inglise keeles, kõik
  sinu arvutis).
- **Tehisintellekti tööriistad moodulitena.** Midagi ei suruta peale: `sos install comfyui` jt,
  üks ühine mudelite hoidla `/srv/ai` ja enne iga allalaadimist kontroll, kas mudel mahub ja mida
  selle litsents lubab.
- **Oma töölaud.** Windowsist tuttavad klahvid töötavad (`Win`, `Win+Tab`, `Alt+Tab`, `Win+D`,
  `Win+nooled`, `Alt+F4`); lisaks lõikelaua ajalugu, emojid, tekst ekraanilt, värvipipett,
  kalkulaator käivitajas, mängurežiim ja õhtuti soojem ekraan.
- **Kõike saab tagasi võtta.** Btrfsi hetktõmmised enne iga uuendust, mooduli muutust ja Jacksoni
  tegevust; `Super+Z` või `sos undo` võtab viimase muudatuse tagasi.

Lubadus: ei mingit reklaami, kontot ega telemeetriat; tehisintellekt ei käivitu kunagi ise; vaikimisi
kõik kohapeal.

## Proovi virtuaalmasinas (umbes 15 minutit)

1. Laadi alla **[sos-26.10-amd64.iso](https://github.com/svoya-os/sos/releases/download/test/sos-26.10-amd64.iso)** (umbes 1,7 GB, üks fail, kontot pole
   vaja): see on `main`-i [testversioon](https://github.com/svoya-os/sos/releases/tag/test).
2. VirtualBox: *Linux / Ubuntu (64-bit)*, 8 GB mälu, 4 protsessorit, *Luba EFI*, graafika
   *VMSVGA* ilma 3D-ta, käivita ISO-ga.
3. Oled live-seansi töölaual. `Super+K` näitab kõiki kiirklahve; **„Install SOS“** Jacksoni
   tervituses paigaldab süsteemi kettale.

## Riistvara

64-bitised arvutid (amd64) UEFI-ga. NVIDIA RTX 20–50: peamine siht; GTX 900/1000: vanem draiver;
AMD Radeon RX 7000/9000 ja Ryzen AI Max: toetatud; Intel Arc: põhivõimalused; ilma videokaardita
töötab kõik, aga kohalik tehisintellekt ainult väikeste mudelitega.

## Rohkem

[Paigaldusjuhend](../guides/install.md) · [Esimesed sammud](../guides/first-steps.md) ·
[Windowsist tulijale](../guides/from-windows.md) · [KKK](../guides/faq.md) (inglise keeles) ·
[Teata veast](https://github.com/svoya-os/sos/issues) · Litsents: Apache-2.0.
