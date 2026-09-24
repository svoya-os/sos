<!-- Thanks for contributing to SOS! Можно по-русски.
     Guide: CONTRIBUTING.md. Security fixes: report privately first, see SECURITY.md. -->

## What and why

<!-- What does this change, and why is it needed? Link issues: "Fixes #123". -->

## How I tested it

<!-- Commands you ran, hardware or VM, what you checked by hand. -->

## Screenshots

<!-- For UI changes: Graphite, Paper and Phosphor, plus reduce-motion if something animates. -->

## Checklist

- [ ] Every commit is signed off (`git commit -s`, DCO).
- [ ] Tests pass locally (`python3 -m unittest`, `shellcheck`, `qmllint` where relevant).
- [ ] User-facing strings exist in English and Russian.
- [ ] Docs and the `Unreleased` section of CHANGELOG.md are updated, if users will notice.
- [ ] New files have an SPDX header or a REUSE.toml entry (`reuse lint`).
- [ ] No new network request, **or** it only happens after the user turns on the feature that
      needs it, and docs/guides/privacy.md is updated.
- [ ] If this touches Jackson's permissions or sandboxing, secrets, packaging, the image or
      installer, or signing: I described the security impact below (two reviews needed).

## Security impact

<!-- Only for security-sensitive areas (see CONTRIBUTING.md). Otherwise delete this section. -->

## AI assistance

<!-- Pick one. If AI did a substantial part, say which parts and which tool, and add an
     "Assisted-by:" trailer to those commits. You must have read and tested everything. -->

- [ ] None, or only autocomplete, spelling and formatting.
- [ ] Substantial. Parts and tool:
