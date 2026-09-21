#!/usr/bin/env python3
"""Claude Code PreToolUse guard for handoff.

Refuses Edit/Write/MultiEdit/NotebookEdit on any project that is currently
handed off to another machine, so the stale local copy cannot drift and get
overwritten by the next `handoff back`.

Exit 2 blocks the tool call and shows stderr to Claude. Every other failure
mode exits 0, so a broken guard can never wedge a session.
"""
import json
import os
import sys

REGISTRY = os.environ.get(
    "HANDOFF_REGISTRY",
    os.path.join(os.environ.get("HANDOFF_STATE_DIR", os.path.expanduser("~/.handoff")),
                 "handoffs.json"),
)
WRITE_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")


def main():
    try:
        raw = sys.stdin.read()
        event = json.loads(raw) if raw.strip() else {}
    except Exception:
        return 0

    if event.get("tool_name") not in WRITE_TOOLS:
        return 0

    path = (event.get("tool_input") or {}).get("file_path")
    if not path:
        return 0

    try:
        registry = json.load(open(REGISTRY))
    except Exception:
        return 0
    if not registry:
        return 0

    try:
        path = os.path.realpath(path)
    except Exception:
        pass

    for root, info in registry.items():
        try:
            real_root = os.path.realpath(root)
        except Exception:
            real_root = root
        if path == real_root or path.startswith(real_root.rstrip("/") + "/"):
            sys.stderr.write(
                "BLOCKED: %s is handed off to %s (session %s, since %s).\n"
                "Its files live on that machine right now, so editing this copy "
                "would be overwritten by the next 'handoff back'.\n"
                "Tell the user to run 'handoff back' in %s to bring it home, or "
                "to work in the remote session instead. Do not edit around this.\n"
                % (
                    os.path.basename(real_root),
                    info.get("host", "the remote"),
                    info.get("session", "?"),
                    info.get("since", "?"),
                    real_root,
                )
            )
            return 2
    return 0


sys.exit(main())
