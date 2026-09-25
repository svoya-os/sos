# SPDX-License-Identifier: Apache-2.0
"""Filesystem layout (docs/ARCHITECTURE.md §3).

Every component receives a :class:`Paths` instance instead of reading the
environment itself, so tests can point Jackson at a temporary home.
"""

from __future__ import annotations

import os
import stat
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


@dataclass(frozen=True)
class Paths:
    home: Path
    config_home: Path   # $XDG_CONFIG_HOME
    data_home: Path     # $XDG_DATA_HOME
    state_home: Path    # $XDG_STATE_HOME
    runtime_base: Path  # $XDG_RUNTIME_DIR (or a private fallback)
    system_config: Path = Path("/etc/svoya")
    system_data: Path = Path("/usr/share/svoya")

    # --- construction -------------------------------------------------
    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None) -> "Paths":
        env = os.environ if env is None else env
        home = Path(env.get("HOME") or os.path.expanduser("~"))

        def xdg(name: str, default: Path) -> Path:
            value = env.get(name, "")
            return Path(value) if value and os.path.isabs(value) else default

        runtime = env.get("XDG_RUNTIME_DIR", "")
        runtime_base = Path(runtime) if runtime and os.path.isabs(runtime) else _runtime_fallback()
        return cls(
            home=home,
            config_home=xdg("XDG_CONFIG_HOME", home / ".config"),
            data_home=xdg("XDG_DATA_HOME", home / ".local" / "share"),
            state_home=xdg("XDG_STATE_HOME", home / ".local" / "state"),
            runtime_base=runtime_base,
        )

    @classmethod
    def for_root(cls, root: Path) -> "Paths":
        """A self-contained layout under *root* (tests, demos)."""
        root = Path(root)
        return cls(
            home=root / "home",
            config_home=root / "home" / ".config",
            data_home=root / "home" / ".local" / "share",
            state_home=root / "home" / ".local" / "state",
            runtime_base=root / "run",
            system_config=root / "etc" / "svoya",
            system_data=root / "usr" / "share" / "svoya",
        )

    # --- svoya-wide ----------------------------------------------------
    @property
    def config_dir(self) -> Path:
        return self.config_home / "svoya"

    @property
    def config_file(self) -> Path:
        return self.config_dir / "jackson.toml"

    @property
    def system_config_file(self) -> Path:
        return self.system_config / "jackson.toml"

    @property
    def secrets_file(self) -> Path:
        return self.config_dir / "secrets.env"

    @property
    def avatar_file(self) -> Path:
        """Jackson's look and name, shared with the shell (DESIGN.md §13)."""
        return self.config_dir / "avatar.json"

    @property
    def svoya_toml(self) -> Path:
        return self.config_dir / "svoya.toml"

    @property
    def ai_off_markers(self) -> tuple[Path, Path]:
        """The AI switch (`sos ai off`): (system-wide, this user)."""
        return self.system_config / "ai.off", self.config_dir / "ai.off"

    @property
    def state_dir(self) -> Path:
        return self.state_home / "svoya"

    @property
    def theme_json(self) -> Path:
        return self.state_dir / "theme.json"

    @property
    def status_json(self) -> Path:
        return self.state_dir / "status.json"

    # --- Jackson data ----------------------------------------------------
    @property
    def data_dir(self) -> Path:
        return self.data_home / "svoya" / "jackson"

    @property
    def memory_dir(self) -> Path:
        return self.data_dir / "memory"

    @property
    def audit_file(self) -> Path:
        return self.data_dir / "audit.jsonl"

    @property
    def audit_head(self) -> Path:
        return self.data_dir / "audit.head"

    @property
    def index_db(self) -> Path:
        return self.data_dir / "index.sqlite"

    @property
    def grants_file(self) -> Path:
        return self.data_dir / "grants.json"

    @property
    def actions_file(self) -> Path:
        return self.data_dir / "actions.jsonl"

    @property
    def undo_store(self) -> Path:
        return self.data_dir / "undo"

    @property
    def skills_dir(self) -> Path:
        return self.data_dir / "skills"

    @property
    def system_skills_dir(self) -> Path:
        """Skills installed by packages (read-only; e.g. the UpsiL skill from the upsil package)."""
        return self.system_data / "jackson" / "skills"

    @property
    def mcp_pins(self) -> Path:
        return self.data_dir / "mcp-pins.json"

    @property
    def spend_file(self) -> Path:
        return self.data_dir / "spend.json"

    @property
    def log_dir(self) -> Path:
        return self.data_dir / "logs"

    @property
    def trash_dir(self) -> Path:
        """freedesktop.org home trash."""
        return self.data_home / "Trash"

    # --- runtime -----------------------------------------------------------
    @property
    def runtime_dir(self) -> Path:
        return self.runtime_base / "svoya"

    @property
    def socket(self) -> Path:
        return self.runtime_dir / "jackson.sock"

    # --- helpers -------------------------------------------------------------
    def ensure_private_dir(self, path: Path) -> Path:
        """Create *path* (and parents) with mode 0700 for the leaf."""
        path.mkdir(parents=True, exist_ok=True)
        try:
            os.chmod(path, 0o700)
        except OSError:
            pass
        return path

    def ensure_runtime_dir(self) -> Path:
        d = self.ensure_private_dir(self.runtime_dir)
        st = os.stat(d)
        if st.st_uid != os.getuid():
            raise PermissionError(f"{d} is owned by uid {st.st_uid}, not {os.getuid()}")
        if stat.S_IMODE(st.st_mode) & 0o077:
            raise PermissionError(f"{d} must not be accessible by other users")
        return d

    def ensure_data_dir(self) -> Path:
        return self.ensure_private_dir(self.data_dir)


def _runtime_fallback() -> Path:
    """Private runtime base when $XDG_RUNTIME_DIR is not set (headless/tests)."""
    uid = os.getuid()
    run_user = Path(f"/run/user/{uid}")
    try:
        if run_user.is_dir() and os.stat(run_user).st_uid == uid:
            return run_user
    except OSError:
        pass
    base = Path(tempfile.gettempdir()) / f"jackson-{uid}"
    try:
        base.mkdir(mode=0o700, exist_ok=True)
        st = os.lstat(base)
        if not stat.S_ISDIR(st.st_mode) or st.st_uid != uid:
            raise PermissionError(f"refusing to use {base}: not a directory owned by uid {uid}")
        os.chmod(base, 0o700)
    except OSError:
        pass
    return base
