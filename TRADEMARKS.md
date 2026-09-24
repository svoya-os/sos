# SOS Trademark Policy

> **Policy draft, not legal advice.** The marks below are not registered yet. This draft
> describes how the project wants its names and logo to be used. It will be reviewed by a lawyer
> before v1.0 and may change. Questions: open an issue, or write to `trademarks@svoya.dev`
> (**TODO:** address not active yet).

## Why a trademark policy

The open-source licenses let anyone use, study, change and share SOS. Names work
differently. When someone downloads something called "SOS", they should get what the name
promises: the system built from our sources, which keeps the promise in
[VISION.md](docs/VISION.md#3-the-promise-published-binding). This policy protects users from
confusion. It is not meant to stop anyone from building on our work.

## The marks

The marks are held by **LIFKURU OÜ** (Estonia) on behalf of the SOS project:

- the names **SOS** and **Svoya Operating System** in English, **«СОС»** and **«Своя
  Операционная Система»** in Russian, when used for operating systems, software or related
  services;
- the **Morse mark**: `··· ——— ···` used as a logo, with the project's rhythm and styling, and
  the logo artwork in [`branding/`](branding/).

We do **not** claim:

- the letters SOS in any other sense, the SOS distress signal, or Morse code in general;
- the name `sos` of the unrelated support tool (sosreport), or its commands;
- the ordinary word «своя» / "svoya";
- the name Jackson / Джексон.

## Uses that need no permission

You can use the names, and the logo where it fits, without asking:

- **To talk about SOS.** Articles, reviews, videos, books, courses, comparisons, criticism
  and parody can name the project and show the logo, as long as nobody could think the project
  made or approved them.
- **In the community.** User groups, meetups, forums, chats, fan sites and non-commercial events
  (for example "SOS community Tallinn"), as long as they are clearly unofficial and have no
  commercial purpose.
- **To pass on the official system.** Mirrors of the official, unmodified images and packages,
  and sharing them for free or for the cost of the medium (for example USB sticks at an event).
- **To describe compatible software.** "X for SOS", "works on SOS", "packaged for
  SOS". Do not use our logo as your application's icon, and do not suggest endorsement.
- **For yourself.** Stickers, T-shirts and similar items made for yourself, or handed out in
  small numbers at community events without profit.

## Modified versions

If you distribute a system that differs from ours (added, removed or changed packages,
different defaults, patched code or different branding), it is your system, and it needs **your
own name and logo**:

- Replace the user-facing name and logo, and replace our branding package (`svoya-branding`)
  with your own.
- You **may** say, as a plain statement of fact, that your system is **"based on SOS"**
  («основано на СОС»), for example in its description, "about" screen or website, as long
  as your own name and logo are clearly more prominent.
- Do not use names that could be confused with ours, such as "SOS Pro", "Svoya OS Lite" or
  «СОС 2».
- Internal technical names may stay, so that your system remains compatible with ours and with
  scripts written for it: `svoya-*` package names, paths like `/usr/share/svoya/`, and the
  `sos`, `svoya` and `j` commands. This policy is about the names and logos users see.
- Development builds are an exception. You may keep the name on builds of a branch or a pull
  request that you make to test or contribute changes, as long as they are clearly labeled as
  unofficial development builds and not distributed as a product.

License notices, such as copyright and attribution lines, are a separate matter: keep them in
every case.

## Commercial use needs permission

Ask first, in writing, for:

- merchandise with the names or the logo that is sold;
- selling computers with SOS preinstalled and using the marks in your marketing. We would
  like to say yes to vendors who ship the system unmodified and have their hardware checked;
- paid products or services whose name contains a mark, or that use the logo (for example
  "SOS Support");
- company names, product names, domain names or social media accounts that contain a mark and
  are used commercially;
- any other commercial use you are unsure about.

## Never allowed

- Suggesting that the project made, endorses or is affiliated with something when it is not.
- Using the marks for malware, scams, phishing, or an "official download" that is not ours.
- Using the marks for software that breaks the promise, such as a build with telemetry or ads
  that still calls itself SOS.
- Names or logos for operating systems or software that are confusingly similar to ours.
- Registering the marks, or anything confusingly similar, as a trademark, company name or domain
  name.

## Using the logo

- Take the artwork from [`branding/`](branding/). Do not redraw, stretch or distort it, and do
  not add effects. Keep clear space around it.
- Keep the rhythm of the mark: three dots, three dashes, three dots. The signal color comes from
  one of the themes (Graphite amber, Paper ink blue, Phosphor green). On busy backgrounds, use a
  single color.
- The artwork is licensed under CC BY-SA 4.0, which covers copyright. This policy covers the
  trademark side. Both apply: you may adapt the artwork under its license, but you may not use
  it as the logo of a different product.

## Asking for permission

Write to `trademarks@svoya.dev` (**TODO:** not active yet) or, for questions that are not
confidential, open an issue with "trademark" in the title. Tell us who you are, what you want to
do, and show an example if you have one. We try to answer within two weeks. Permission is given
in writing, for a specific use, and can be withdrawn if the use changes.

## Other trademarks

SOS uses Ubuntu 26.04 LTS packages as its engine. It is not Ubuntu, and it is not affiliated
with or endorsed by Canonical Ltd. Ubuntu is a registered trademark of Canonical Ltd. NVIDIA, AMD,
Intel and other names in this repository are trademarks of their owners and are used only to
refer to their products.

## Credits

The structure of this policy follows the
[Arch Linux trademark policy](https://terms.archlinux.org/docs/trademark-policy/), which was
itself adapted from Ubuntu's. The wording here is our own.

---

## Кратко по-русски

> Черновик, не юридическая консультация. Знаки пока не зарегистрированы.

- **Знаки:** названия «СОС» и «Своя Операционная Система», по-английски SOS и Svoya Operating
  System (для ОС, программ и связанных услуг), и знак `··· ——— ···` как логотип. Их держит
  LIFKURU OÜ (Эстония) от имени проекта. На буквы SOS в другом смысле, сигнал бедствия, азбуку
  Морзе, утилиту `sos` (sosreport), обычное слово «своя» и имя «Джексон» мы не претендуем.
- **Без разрешения можно:** писать и снимать о СОС, делать сообщества и некоммерческие
  встречи (с пометкой, что они неофициальные), раздавать официальные неизменённые образы,
  писать «программа для СОС», делать мерч для себя.
- **Изменённые сборки** называй по-своему и ставь свой логотип. Писать «основано на СОС»
  можно. Технические имена (пакеты `svoya-*`, пути `/usr/share/svoya/`, команды `sos`, `svoya`
  и `j`) менять не обязательно.
- **Коммерческое использование** (мерч на продажу, предустановка с нашими знаками в рекламе,
  платные услуги с нашим именем, названия компаний и доменов) — только с письменного разрешения.
- **Никогда нельзя:** выдавать себя за проект, распространять под нашим именем вредоносные
  сборки или сборки с рекламой и телеметрией, регистрировать похожие названия.
