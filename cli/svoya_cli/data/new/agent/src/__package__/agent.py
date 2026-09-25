"""A small tool-using agent for the local model server — standard library only.

Server: `systemctl --user start svoya-llm` (llama.cpp, OpenAI-compatible, 127.0.0.1:8080).
Run:    sos run src/{{ project.package }}/agent.py "What is in README.md?"
The only tool reads files inside this project; everything stays on the machine.
"""
import json
import os
import sys
import urllib.request
from pathlib import Path

BASE = os.environ.get("OPENAI_BASE_URL", "http://127.0.0.1:8080/v1")
MODEL = os.environ.get("AGENT_MODEL", "{{ run.model }}")
ROOT = Path.cwd().resolve()
TOOLS = [{"type": "function", "function": {
    "name": "read_file", "description": "Read a UTF-8 text file inside the project",
    "parameters": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]}}}]


def read_file(path: str) -> str:
    p = (ROOT / path).resolve()
    if ROOT not in p.parents:
        return "denied: outside the project"
    try:
        return p.read_text(encoding="utf-8")[:20000]
    except OSError as e:
        return f"error: {e}"


def chat(messages: list[dict]) -> dict:
    body = json.dumps({"model": MODEL, "messages": messages, "tools": TOOLS}).encode()
    req = urllib.request.Request(f"{BASE}/chat/completions", data=body, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return json.load(r)


def main() -> None:
    question = " ".join(sys.argv[1:]) or "Summarize README.md in two sentences."
    messages = [{"role": "user", "content": question}]
    for _ in range(6):
        msg = chat(messages)["choices"][0]["message"]
        messages.append(msg)
        calls = msg.get("tool_calls") or []
        if not calls:
            print(msg.get("content", ""))
            return
        for call in calls:
            args = json.loads(call["function"].get("arguments") or "{}")
            messages.append({"role": "tool", "tool_call_id": call["id"], "content": read_file(args.get("path", ""))})
    print("(stopped after 6 tool calls)")


if __name__ == "__main__":
    main()
