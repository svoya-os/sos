# Security Policy

SOS gives an AI assistant real access to a real computer. We take that seriously: Jackson
runs tools in sandboxes, asks before risky actions, logs every action in a tamper-evident log
and can undo what it did (see [ARCHITECTURE.md §4.4](docs/ARCHITECTURE.md#44-permission-tiers-jackson-and-every-agent-it-runs)).
If any of that fails, we want to know first.

## Supported versions

SOS is **pre-alpha**. No release has been published yet.

| Version | Security fixes |
|---|---|
| `main` branch | Yes. Fixes land here first. |
| v0.x pre-releases (from v0.1 on) | The latest pre-release only. |
| v1.0 and later | The support policy will be published with v1.0 (see the [roadmap](docs/ROADMAP.md)). |

Packages from the Ubuntu 26.04 LTS engine get security updates from Ubuntu. They reach you
through the normal `sos update` path, which takes a snapshot first.

## Reporting a vulnerability

**Please do not report vulnerabilities in public issues, pull requests or discussions.**

- **Preferred:** GitHub private vulnerability reporting, under
  [Security → Report a vulnerability](https://github.com/svoya-os/sos/security/advisories/new).
  Only the maintainers can see the report.
- **Email:** `security@svoya.dev`. **TODO: not active yet.** Until it is, use GitHub. An
  encryption key will be published here when the address works.

English or Russian are both fine. Please include:

- the affected component (Jackson, the `sos` command, Svoya Shell, installer, image, packages…) and
  the version or commit;
- what an attacker can do, and under which conditions;
- steps to reproduce or a proof of concept;
- **whether you know or suspect that it is being exploited** (this changes our deadlines, see
  [below](#eu-cyber-resilience-act));
- how you would like to be credited.

Reports made with the help of AI tools are welcome, as long as you have reproduced the problem
yourself. We close unverified generated reports without further review.

## What happens next

We are a small project. These are targets, not guarantees:

| Step | Target |
|---|---|
| Acknowledge your report | within 3 working days |
| First assessment (confirmed? severity? scope?) | within 7 days |
| Fix for critical issues | within 30 days |
| Fix for high-severity issues | within 60 days |
| Other issues | in a regular release |
| Status updates to you | at least every 14 days until closed |

We rate severity with CVSS v4.0 as a guide. We publish a GitHub Security Advisory for every
confirmed vulnerability and request a CVE ID through GitHub. Disclosure is coordinated with you:
by default, when the fix ships, and no later than 90 days after your report unless we agree on
something else. Actively exploited issues go faster.

We credit reporters in the advisory and the release notes, unless you prefer not to be named.
There is no bug bounty.

## Scope

**In scope:**

- **Jackson sandbox escapes:** a tool or agent (Claude Code, Codex, OpenCode, goose…) leaving its
  container or microVM, or reaching files, devices, network or your desktop session beyond what
  was granted.
- **Permission bypass:** a tier T2–T4 action without the required approval; an executed action
  that differs from the preview you approved; an "always in this project" grant that applies
  outside its project; untrusted content (web pages, downloaded files, tool output) sending data
  out without a T2 confirmation. Prompt injection is in scope when it leads to any of these.
- **Audit log and undo:** changes to the hash-chained audit log that go undetected; Jackson
  actions missing from the log; undo that silently fails or restores the wrong state.
- **Secrets:** API keys or other secrets reaching logs, prompts, other users, other processes or
  the network.
- **Privacy promise:** any network request made without you having turned on the feature that
  needs it, any telemetry, or data leaving the machine without being shown. The promise is in
  the [README](README.md#the-promise); details in [privacy.md](docs/guides/privacy.md).
- **Supply chain:** our APT repository and its signing keys, package builds and maintainer
  scripts, CI/CD and the release pipeline, module catalog scripts, model store metadata (hashes,
  sources, license flags), ISO checksums and signatures.
- **Installer and boot:** disk encryption, account and password handling, the boot chain as we
  configure it, insecure defaults on the installed system.
- **Svoya Shell:** lock screen or greeter bypass; clipboard, selection or screenshots reaching
  Jackson without a user action.
- **The `sos` command:** privilege escalation through its commands or polkit policies.

**Out of scope** (please report upstream):

- Vulnerabilities in Ubuntu packages that we ship unchanged. Report them to Ubuntu's security
  team. Tell us too if our configuration makes them worse.
- Vulnerabilities in third-party applications, models, agents or cloud providers. If Svoya's
  sandbox fails to contain them, that part is in scope.
- Getting a model to produce harmful or false text without defeating any of Svoya's controls.
- Attacks that need root, or physical access to an unlocked machine.
- Scanner output without a demonstrated impact.

## Good-faith research

If you follow this policy, avoid harming other people's data or systems, and give us reasonable
time to fix the problem before disclosure, we will not take legal action against you, and we
will work with you to understand and fix the problem quickly.

## EU Cyber Resilience Act

SOS is free and open-source software maintained by LIFKURU OÜ, a company established in
Estonia. Our current reading is that LIFKURU OÜ acts as an **open-source software steward** under
the Cyber Resilience Act (Regulation (EU) 2024/2847, Article 24), not as a manufacturer. This is
not legal advice. We will review it whenever the way SOS is distributed or funded changes.

- Since **11 September 2026**, manufacturers must report actively exploited vulnerabilities and
  severe incidents through the Single Reporting Platform run by ENISA: an early warning within
  24 hours, a notification within 72 hours and a final report within 14 days after a fix is
  available.
- Stewards have lighter duties: a documented cybersecurity policy (this file is part of ours),
  cooperation with market surveillance authorities, and reporting under Article 24(3). According
  to the European Commission, the stewards' reporting obligations apply from **11 December 2027**.
- We intend to follow the manufacturer timelines voluntarily from our first public release. If
  we learn that a vulnerability in SOS is actively exploited, we will notify the CSIRT
  designated as coordinator in Estonia through the Single Reporting Platform, and tell affected
  users how to protect themselves.

---

**Кратко по-русски.** Об уязвимостях не пиши в открытые issue. Сообщай закрыто через GitHub:
[Security → Report a vulnerability](https://github.com/svoya-os/sos/security/advisories/new).
Можно писать по-русски. Ответим в течение трёх рабочих дней, первую оценку дадим в течение
недели. Особенно важно: побег из песочницы Джексона, обход подтверждений и уровней разрешений,
утечка ключей, любые сетевые запросы без твоего согласия, атаки на цепочку поставки (APT,
сборка, подписи) и на установщик.
