# SPDX-License-Identifier: Apache-2.0
"""Built-in tools. MCP tools are added at runtime by :class:`.mcp.McpManager`."""

from __future__ import annotations

from ..config import Config
from . import fs, memory_tools, shell, system, web
from .base import (T0, T1, T2, T3, T4, Assessment, Tool, ToolContext, ToolRegistry, ToolResult, UndoSpec,
                   validate_args, wire_name)

__all__ = ["T0", "T1", "T2", "T3", "T4", "Assessment", "Tool", "ToolContext", "ToolRegistry", "ToolResult",
           "UndoSpec", "builtin_tools", "default_registry", "validate_args", "wire_name"]


def builtin_tools(config: Config) -> list[Tool]:
    tools = fs.tools() + system.tools() + memory_tools.tools()
    if config.tools.shell:
        tools += shell.tools()
    if config.tools.web_fetch:
        tools += web.tools()
    if not config.memory.enabled:
        tools = [t for t in tools if not t.name.startswith("memory.")]
    return tools


def default_registry(config: Config) -> ToolRegistry:
    registry = ToolRegistry()
    for tool in builtin_tools(config):
        registry.register(tool)
    return registry
