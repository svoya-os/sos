# SPDX-License-Identifier: Apache-2.0
"""A tiny MCP server over stdio for tests.

    fake_mcp_server.py --mode modern|legacy|silent-legacy [--desc TEXT] [--state FILE]

modern:         answers server/discover, requires _meta.protocolVersion on every request
legacy:         answers -32601 to server/discover before initialize, then the 2025-11-25 flow
silent-legacy:  ignores unknown pre-initialize requests entirely (the client must time out)
"""

import argparse
import json
import sys

parser = argparse.ArgumentParser()
parser.add_argument("--mode", default="modern")
parser.add_argument("--desc", default="Echo text back")
args = parser.parse_args()

initialized = False
TOOLS = [
    {"name": "echo", "description": args.desc,
     "inputSchema": {"type": "object", "properties": {"text": {"type": "string"}}, "required": ["text"]}},
    {"name": "add", "description": "Add two numbers",
     "inputSchema": {"type": "object", "properties": {"a": {"type": "number"}, "b": {"type": "number"}}}},
]


def send(msg):
    sys.stdout.write(json.dumps(msg) + "\n")
    sys.stdout.flush()


def result(req_id, res):
    send({"jsonrpc": "2.0", "id": req_id, "result": res})


def error(req_id, code, message, data=None):
    err = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    send({"jsonrpc": "2.0", "id": req_id, "error": err})


for line in sys.stdin:
    try:
        msg = json.loads(line)
    except ValueError:
        continue
    method, req_id = msg.get("method"), msg.get("id")
    params = msg.get("params") or {}
    if req_id is None:
        if method == "notifications/initialized":
            initialized = True
        continue
    meta = params.get("_meta") or {}
    if args.mode == "modern":
        version = meta.get("io.modelcontextprotocol/protocolVersion")
        if version is None:
            error(req_id, -32602, "missing _meta protocol version")
            continue
        if version != "2026-07-28":
            error(req_id, -32022, "Unsupported protocol version",
                  {"supported": ["2026-07-28"], "requested": version})
            continue
        if method == "server/discover":
            result(req_id, {"resultType": "complete", "supportedVersions": ["2026-07-28"],
                            "capabilities": {"tools": {}},
                            "_meta": {"io.modelcontextprotocol/serverInfo": {"name": "fake", "version": "1"}}})
            continue
    else:
        if not initialized and method != "initialize":
            if args.mode == "silent-legacy":
                continue
            error(req_id, -32601, "Method not found")
            continue
        if method == "initialize":
            result(req_id, {"protocolVersion": "2025-11-25", "capabilities": {"tools": {}},
                            "serverInfo": {"name": "fake-legacy", "version": "1"}})
            continue
    if method == "tools/list":
        result(req_id, {"resultType": "complete", "tools": TOOLS})
    elif method == "tools/call":
        name = params.get("name")
        a = params.get("arguments") or {}
        if name == "echo":
            result(req_id, {"resultType": "complete", "content": [{"type": "text", "text": f"echo: {a.get('text')}"}],
                            "isError": False})
        elif name == "add":
            total = a.get("a", 0) + a.get("b", 0)
            result(req_id, {"resultType": "complete", "content": [{"type": "text", "text": str(total)}],
                            "structuredContent": {"sum": total}})
        else:
            error(req_id, -32602, f"Unknown tool: {name}")
    else:
        error(req_id, -32601, "Method not found")
