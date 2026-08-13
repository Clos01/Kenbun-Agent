#!/usr/bin/env python3
import argparse
import subprocess
import json
import os
import sys
import select

def main():
    parser = argparse.ArgumentParser(description="Kenbun Tool Runner - Execute any MCP tool from the terminal.")
    parser.add_argument("--tool", required=True, help="Name of the tool (e.g., orchestrate, review_code_with_gemini, consult_supervisor)")
    parser.add_argument("--args", help="JSON string of arguments")
    parser.add_argument("--file", help="Path to a file to inject as 'code_snippet' or 'content' key in arguments")
    parser.add_argument("--timeout", type=float, default=180.0, help="Response timeout in seconds (default: 180)")

    args = parser.parse_args()

    # Parse arguments
    tool_args = {}
    if args.args:
        try:
            tool_args = json.loads(args.args)
        except json.JSONDecodeError as e:
            print(f"Error parsing --args JSON: {e}", file=sys.stderr)
            sys.exit(1)

    # Inject file content if requested
    if args.file:
        if not os.path.exists(args.file):
            print(f"Error: File not found at {args.file}", file=sys.stderr)
            sys.exit(1)
        with open(args.file, "r", encoding="utf-8") as f:
            content = f.read()
        
        # Decide which parameter to inject into
        if args.tool in ["review_code_with_gemini", "consult_supervisor", "orchestrate"]:
            tool_args["code_snippet"] = content
        else:
            tool_args["content"] = content

    # Set up environment
    env = os.environ.copy()
    base_dir = "/Users/carlosrivas/Dev/Kenbun"
    env["PYTHONPATH"] = f"{base_dir}/core:{base_dir}/core/tools:{base_dir}"

    print(f"🚀 Starting Kenbun MCP Server and executing tool '{args.tool}'...", file=sys.stderr)

    # Spawn MCP server
    python_bin = f"{base_dir}/core/.venv/bin/python3"
    server_script = f"{base_dir}/core/tools/infrastructure/server.py"
    
    p = subprocess.Popen(
        [python_bin, "-u", server_script],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        env=env,
        text=True
    )

    try:
        # 1. JSON-RPC Initialize Handshake
        init_req = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "kenbun-cli-runner", "version": "1.0.0"}
            }
        }
        p.stdin.write(json.dumps(init_req) + "\n")
        p.stdin.flush()

        # Read initialize response
        init_resp = p.stdout.readline()
        if not init_resp:
            print("Error: MCP server failed to initialize (empty response)", file=sys.stderr)
            sys.exit(1)

        # 2. Call the tool
        call_req = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": args.tool,
                "arguments": tool_args
            }
        }
        p.stdin.write(json.dumps(call_req) + "\n")
        p.stdin.flush()

        # 3. Read response with timeout
        r, _, _ = select.select([p.stdout], [], [], args.timeout)
        if r:
            resp_line = p.stdout.readline()
            if not resp_line:
                print("Error: Empty response from MCP server", file=sys.stderr)
                sys.exit(1)
            
            try:
                resp_json = json.loads(resp_line)
                if "error" in resp_json:
                    print(f"❌ Tool execution failed: {json.dumps(resp_json['error'], indent=2)}", file=sys.stderr)
                    sys.exit(1)
                
                result = resp_json.get("result", {})
                content_list = result.get("content", [])
                
                # Print the content blocks returned by the tool
                for item in content_list:
                    if isinstance(item, dict):
                        if item.get("type") == "text":
                            print(item.get("text", ""))
                        else:
                            print(json.dumps(item, indent=2))
                    else:
                        print(item)
            except json.JSONDecodeError:
                # Fallback to printing raw output if it wasn't valid JSON-RPC
                print(resp_line)
        else:
            print("❌ Timeout: Tool execution took too long.", file=sys.stderr)
            sys.exit(1)

    finally:
        p.terminate()
        try:
            p.wait(timeout=2.0)
        except subprocess.TimeoutExpired:
            p.kill()

if __name__ == "__main__":
    main()
