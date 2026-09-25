# SPDX-License-Identifier: Apache-2.0
"""`python3 -m jackson …` is the same as the `jackson` command."""

from .cli import main

raise SystemExit(main())
