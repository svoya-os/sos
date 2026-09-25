# SPDX-License-Identifier: Apache-2.0
"""Jackson (Джексон) — the assistant of SOS («СОС — Своя Операционная Система»).

Jackson routes requests to local or cloud models, runs tools and agents inside
sandboxes, asks before anything risky with an exact preview, keeps a
tamper-evident audit log and undoes its own actions.

Runtime dependencies: the Python standard library only.
"""

__version__ = "0.1.0"

#: Version of the JSON Lines socket protocol (docs/ARCHITECTURE.md §4.3).
PROTOCOL_VERSION = 1
