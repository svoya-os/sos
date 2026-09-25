# SPDX-License-Identifier: Apache-2.0
"""External agents (Claude Code, Codex CLI, OpenCode, goose) — documented interface, not in v0.1.

Modules install these agents on demand (`sos modules add agents`). Jackson will launch them over
the Agent Client Protocol (ACP: JSON-RPC 2.0 over the agent's stdio) inside the same sandbox and
permission model as its own tools:

* the agent process runs under bubblewrap (project folder read-write, no secrets, network only
  when the user allowed it);
* every file edit / command the agent asks for through ACP (``fs/write_text_file``,
  ``terminal/create``, ``session/request_permission``) is mapped to a Jackson tool call, so it
  gets a tier, an approval card with the exact preview, an audit entry and an undo record;
* the agent's own model traffic is shown as "data left the machine" with the provider name.

The interface the v0.3 «Поводок» implementation will satisfy:
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import AsyncIterator, Protocol


@dataclass
class AgentSpec:
    id: str                         # "claude-code", "codex", "opencode", "goose"
    command: list[str]              # e.g. ["claude-code-acp"]
    network: bool = True            # agents talk to their model provider
    env_keys: list[str] = field(default_factory=list)   # keyring entries to expose, e.g. ["anthropic"]


class ExternalAgent(Protocol):
    async def start(self, spec: AgentSpec, project: str) -> None: ...
    async def prompt(self, text: str) -> AsyncIterator[dict]: ...   # yields Jackson protocol events
    async def cancel(self) -> None: ...
    async def stop(self) -> None: ...
