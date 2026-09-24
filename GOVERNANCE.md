# Governance

How decisions are made in SOS today, and how that will change as the project grows.

## Today: a project lead with the final say

SOS is young and has one lead: **Maksim**, the founder, who maintains the project through
**LIFKURU OÜ** (Estonia). This is the "benevolent dictator" model (BDFL): the lead has the final
say on direction, merges, releases and Code of Conduct enforcement. At this stage it keeps the
design coherent and lets the project move quickly.

That power has limits:

- **The promise binds the lead too.** The promise in [VISION.md §3](docs/VISION.md#3-the-promise-published-binding)
  (no ads, no telemetry, AI never starts by itself, local by default, everything reversible) is
  not a preference that can be quietly dropped. See [The promise](#the-promise) below.
- **Decisions happen in public:** in issues, in pull requests and in decision records.
- **Anyone can fork.** The code is Apache-2.0. A fork needs its own name
  (see [TRADEMARKS.md](TRADEMARKS.md)), but nothing else stands in its way.

## Roles

| Role | Who | Can |
|---|---|---|
| User | anyone | report bugs and hardware, propose ideas, join discussions |
| Contributor | anyone with a merged contribution | everything above; be invited to become a maintainer |
| Maintainer | invited contributors, listed in [.github/CODEOWNERS](.github/CODEOWNERS) | review, merge and triage in their areas |
| Key holder | at least two people per signing key (see below) | sign packages and releases |
| Project lead | Maksim | final say until the council exists |

Maintainers are invited by the project lead (later: by the council) after a period of steady,
careful contributions and reviews. A maintainer who has been inactive for six months moves to
emeritus status and can come back by asking.

## How decisions are made

**Everyday changes** go through pull requests. A maintainer of the area reviews and merges.
Disagreements are discussed in the pull request. If they cannot be settled there, the project
lead decides.

**Significant decisions** get a **decision record**: a short Markdown file in
`docs/decisions/`, named `NNNN-short-title.md` (the directory is created with the first record).
A record states the context, the options considered, the decision, its consequences and its
status (`proposed`, `accepted`, `superseded by NNNN`). A decision record is needed for:

- changes to interfaces in [ARCHITECTURE.md](docs/ARCHITECTURE.md);
- new components or runtime dependencies;
- the security model: permission tiers, sandboxing, audit, signing;
- licensing, trademarks and this governance document;
- anything that touches the promise.

Decision records are proposed as pull requests and stay open for comment for at least
**7 days**, or **30 days** for licensing, governance and the promise. The project lead (later:
the council) accepts or rejects them and writes down why.

### The promise

The promise can be strengthened like any other decision. Weakening it requires a decision
record, at least 30 days of public comment, and a clear notice in the release notes before the
release that contains the change. We expect to turn such proposals down.

## Signing keys

SOS signs its APT repository and its release checksums. Keys have not been created yet.
These rules apply from the moment they are:

- **Every signing key has at least two key holders**, so the project survives the loss of any
  one person. Key holders are named in a decision record, and key fingerprints are published in
  the repository and on the website.
- Primary keys are created and kept offline (hardware tokens or air-gapped storage). Day-to-day
  signing uses subkeys that can be revoked without replacing the primary key. Subkeys expire and
  are renewed at least every two years.
- Revocation certificates are stored offline, separately from the keys.
- A change of keys or key holders requires a decision record and a public announcement.
- If a key is lost or compromised, we revoke it, publish a security advisory and rotate to a new
  key.
- **No stable release (v1.0 or later) ships before there are two key holders.** Until then,
  pre-releases may be signed by the project lead alone, and their release notes say so.

## Towards a maintainer council

The single-lead model is a starting point. When at least three maintainers, including the lead,
have been active for six months, a **maintainer council** of three to five maintainers takes over
the final say. We aim to get there before v1.0.

- The council decides by consensus. When consensus fails, it votes, and the simple majority wins.
  The project lead chairs the council and breaks ties.
- Council members with a conflict of interest in a decision do not vote on it.
- LIFKURU OÜ holds the trademarks, domains and signing infrastructure for the project and
  follows the council's decisions on their use. Whether they should move to a neutral non-profit
  home is a question for the council.
- The move to a council is itself recorded in a decision record, together with the updated
  version of this document.

## Code of Conduct enforcement

The project lead handles [Code of Conduct](CODE_OF_CONDUCT.md) reports today. Once the council
exists, it appoints at least two people to handle reports. Anyone involved in a report does not
take part in handling it.

## Money and commercial interests

The project does not take funding yet (see [.github/FUNDING.yml](.github/FUNDING.yml)). If
LIFKURU OÜ or anyone else offers paid services around SOS, the promise still holds: nothing
in the OS advertises or upsells them, and no feature is held back from the free system for them.

## Changing this document

Changes to this document are significant decisions: a decision record and at least 30 days of
public comment.

---

**Кратко по-русски.** Сейчас у проекта один руководитель с решающим голосом — Максим
(LIFKURU OÜ, Эстония). Его тоже связывает обещание из [VISION.md](docs/VISION.md): ослабить его
можно только через открытое решение с обсуждением не меньше 30 дней, и мы ожидаем, что такие
предложения будем отклонять. Важные решения записываются в `docs/decisions/`. У каждого ключа
подписи минимум два хранителя; без второго хранителя стабильный релиз (v1.0) не выйдет. Когда
в проекте будет хотя бы три активных мейнтейнера, решающий голос перейдёт к совету
мейнтейнеров.
