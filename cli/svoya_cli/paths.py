"""Filesystem locations (docs/ARCHITECTURE.md §3).

Every location can be overridden through an environment variable so tests and dev checkouts
never touch the real system:

  SVOYA_ROOT            prefix for system paths (/sys, /proc, /etc, /var, /usr, /srv, /dev, /boot, /lib)
  SVOYA_AI_ROOT         model & dataset store                 (default /srv/ai)
  SVOYA_REGISTRY        model registry database               (default $SVOYA_AI_ROOT/registry.db)
  SVOYA_VAR_LIB         system state                          (default /var/lib/svoya)
  SVOYA_THEMES_DIR      theme tokens                          (default /usr/share/svoya/themes)
  SVOYA_TEMPLATES_DIR   theme templates                       (default /usr/share/svoya/templates)
  SVOYA_MODULES_DIR     module catalog                        (default /usr/share/svoya/modules)
  SVOYA_SHELL_DIR       Quickshell config                     (default /usr/share/svoya/shell)

When svoya runs from a source checkout (``cli/svoya_cli`` next to ``themes/`` and ``modules/``),
the checkout's resources are used instead of ``/usr/share/svoya``.
"""
from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

REPO_ROOT = Path(__file__).resolve().parents[2]


def _in_checkout() -> bool:
    return (REPO_ROOT / "cli" / "svoya_cli").is_dir() and (REPO_ROOT / "themes").is_dir()


class Paths:
    """Resolved locations for one invocation (user + system)."""

    def __init__(self, env: Mapping[str, str] | None = None, home: str | os.PathLike | None = None):
        self.env: Mapping[str, str] = os.environ if env is None else env
        e = self.env
        self.root = Path(e.get("SVOYA_ROOT") or "/")
        self.home = Path(home or e.get("HOME") or os.path.expanduser("~"))
        self.config_home = Path(e.get("XDG_CONFIG_HOME") or self.home / ".config")
        self.state_home = Path(e.get("XDG_STATE_HOME") or self.home / ".local" / "state")
        self.data_home = Path(e.get("XDG_DATA_HOME") or self.home / ".local" / "share")
        self.cache_home = Path(e.get("XDG_CACHE_HOME") or self.home / ".cache")
        self.runtime_dir = Path(e.get("XDG_RUNTIME_DIR") or f"/run/user/{os.getuid()}")
        self.dev = _in_checkout()

    # ---- system paths (prefixed by SVOYA_ROOT for tests) ----
    def sys(self, path: str) -> Path:
        """Map an absolute system path (``/sys/...``) into the (possibly fake) root."""
        return self.root / path.lstrip("/")

    # ---- user ----
    @property
    def user_config_dir(self) -> Path:
        return self.config_home / "svoya"

    @property
    def user_config(self) -> Path:
        return self.user_config_dir / "svoya.toml"

    @property
    def first_run_marker(self) -> Path:
        return self.user_config_dir / "first-run-done"

    @property
    def state_dir(self) -> Path:
        return self.state_home / "svoya"

    @property
    def jobs_dir(self) -> Path:
        return self.state_dir / "jobs"

    @property
    def cache_dir(self) -> Path:
        return self.state_dir / "cache"

    @property
    def theme_json(self) -> Path:
        return self.state_dir / "theme.json"

    @property
    def status_json(self) -> Path:
        return self.state_dir / "status.json"

    @property
    def runtime_svoya(self) -> Path:
        return self.runtime_dir / "svoya"

    # ---- system ----
    @property
    def system_config(self) -> Path:
        return self.sys("/etc/svoya/svoya.toml")

    @property
    def var_lib(self) -> Path:
        v = self.env.get("SVOYA_VAR_LIB")
        return Path(v) if v else self.sys("/var/lib/svoya")

    @property
    def modules_state(self) -> Path:
        return self.var_lib / "modules.json"

    @property
    def history_file(self) -> Path:
        return self.var_lib / "history.json"

    @property
    def ai_root(self) -> Path:
        v = self.env.get("SVOYA_AI_ROOT")
        return Path(v) if v else self.sys("/srv/ai")

    @property
    def registry_db(self) -> Path:
        v = self.env.get("SVOYA_REGISTRY")
        return Path(v) if v else self.ai_root / "registry.db"

    def _resource(self, env_key: str, system: str, repo_rel: str) -> Path:
        v = self.env.get(env_key)
        if v:
            return Path(v)
        if self.dev and (REPO_ROOT / repo_rel).exists():
            return REPO_ROOT / repo_rel
        return self.sys(system)

    @property
    def themes_dir(self) -> Path:
        return self._resource("SVOYA_THEMES_DIR", "/usr/share/svoya/themes", "themes")

    @property
    def user_themes_dir(self) -> Path:
        return self.data_home / "svoya" / "themes"

    @property
    def templates_dir(self) -> Path:
        return self._resource("SVOYA_TEMPLATES_DIR", "/usr/share/svoya/templates", "themes/templates")

    @property
    def modules_dir(self) -> Path:
        return self._resource("SVOYA_MODULES_DIR", "/usr/share/svoya/modules", "modules")

    @property
    def shell_dir(self) -> Path:
        v = self.env.get("SVOYA_SHELL_DIR")
        return Path(v) if v else Path("/usr/share/svoya/shell")

    @property
    def data_dir(self) -> Path:
        """Package data shipped inside svoya_cli (model catalog, project templates)."""
        return Path(__file__).resolve().parent / "data"
