"""Tiny newline-delimited JSON-RPC MCP server used by the stdio client test."""
import json
import os
import sys

TOOLS = [{"name": "echo", "description": "Echo text", "inputSchema": {"type": "object"}}]

for line in sys.stdin:
    msg = json.loads(line)
    method, rid = msg.get("method"), msg.get("id")
    if rid is None:
        continue  # notification
    if method == "initialize":
        result = {"protocolVersion": "2025-06-18", "capabilities": {"tools": {}}, "serverInfo": {"name": "fake"}}
    elif method == "tools/list":
        result = {"tools": TOOLS}
    elif method == "tools/call":
        args = msg["params"]["arguments"]
        text = args.get("text", "") + "|" + os.environ.get("FAKE_MCP_SECRET", "")
        result = {"content": [{"type": "text", "text": text}]}
    else:
        print(json.dumps({"jsonrpc": "2.0", "id": rid, "error": {"code": -32601, "message": "nope"}}), flush=True)
        continue
    print(json.dumps({"jsonrpc": "2.0", "id": rid, "result": result}), flush=True)
