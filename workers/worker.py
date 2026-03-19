#!/usr/bin/env python3
"""
Project Sovereign — Worker Agent
A single-purpose agent that picks up one task, executes it, writes the result, and exits.
"""

import json
import os
import sys
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

import anthropic
from dotenv import load_dotenv

load_dotenv()

# ── Config from environment (set by CEO orchestrator) ───────────────────
WORKER_ID = os.getenv("WORKER_ID", "unknown")
WORKER_ROLE = os.getenv("WORKER_ROLE", "coder")
TASK_FILE = os.getenv("TASK_FILE", "")
MAX_TOKENS = int(os.getenv("WORKER_MAX_TOKENS", "8096"))
MODEL = os.getenv("WORKER_MODEL", "claude-sonnet-4-20250514")

BASE_DIR = Path("/root/sovereign")
SHARED_DIR = BASE_DIR / "shared"
RESULTS_DIR = SHARED_DIR / "results"
PROFILES_DIR = BASE_DIR / "profiles"

# ── Pricing ─────────────────────────────────────────────────────────────
PRICING = {"input": 3.00, "output": 15.00, "cache_read": 0.30, "cache_write": 3.75}


def estimate_cost(usage) -> float:
    input_cost = (usage.input_tokens / 1_000_000) * PRICING["input"]
    output_cost = (usage.output_tokens / 1_000_000) * PRICING["output"]
    return input_cost + output_cost


def load_profile(role: str) -> str:
    profile_path = PROFILES_DIR / f"{role}.md"
    if profile_path.exists():
        return profile_path.read_text()
    return f"You are a {role} agent. Complete the assigned task precisely."


def build_tools(role: str) -> list[dict]:
    """Workers get minimal tools based on their role."""
    tools = [
        {
            "name": "write_file",
            "description": "Write content to a file in the shared workspace.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path relative to shared/"},
                    "content": {"type": "string", "description": "File content"},
                },
                "required": ["path", "content"],
            },
        },
        {
            "name": "read_file",
            "description": "Read a file from the shared workspace.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path relative to shared/"},
                },
                "required": ["path"],
            },
        },
    ]

    # Only researcher gets internet access
    if role == "researcher":
        tools.append({
            "name": "fetch_url",
            "description": "Fetch content from a URL via HTTP GET.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "URL to fetch"},
                },
                "required": ["url"],
            },
        })

    return tools


def handle_tool_call(tool_name: str, tool_input: dict) -> str:
    if tool_name == "read_file":
        target = SHARED_DIR / tool_input["path"]
        if not target.exists():
            return f"Error: File not found: {tool_input['path']}"
        return target.read_text()[:50_000]

    elif tool_name == "write_file":
        target = SHARED_DIR / tool_input["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(tool_input["content"])
        return f"OK: Written {len(tool_input['content'])} bytes to {target}"

    elif tool_name == "fetch_url":
        try:
            req = urllib.request.Request(
                tool_input["url"],
                headers={"User-Agent": "Sovereign-Worker/1.0"},
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8", errors="replace")[:50_000]
        except Exception as e:
            return f"Fetch error: {e}"

    return f"Unknown tool: {tool_name}"


def run_worker():
    """Execute a single task and exit."""
    if not TASK_FILE:
        print(f"[Worker-{WORKER_ID}] ERROR: No TASK_FILE specified.")
        sys.exit(1)

    task_path = SHARED_DIR / "tasks" / TASK_FILE
    if not task_path.exists():
        print(f"[Worker-{WORKER_ID}] ERROR: Task file not found: {task_path}")
        sys.exit(1)

    task = json.loads(task_path.read_text())
    task_id = task.get("task_id", TASK_FILE)
    print(f"[Worker-{WORKER_ID}] Role: {WORKER_ROLE} | Task: {task_id}")

    client = anthropic.Anthropic()
    system_prompt = load_profile(WORKER_ROLE)
    tools = build_tools(WORKER_ROLE)
    total_cost = 0.0

    messages = [
        {
            "role": "user",
            "content": (
                f"Here is your task assignment:\n\n```json\n{json.dumps(task, indent=2)}\n```\n\n"
                f"Execute this task. Write your result to results/{task_id}.json"
            ),
        }
    ]

    # Agentic loop — worker keeps going until done or max 20 iterations
    for iteration in range(20):
        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=system_prompt,
                tools=tools,
                messages=messages,
            )
        except anthropic.APIError as e:
            print(f"[Worker-{WORKER_ID}] API Error: {e}")
            write_error_result(task_id, str(e))
            sys.exit(1)

        cost = estimate_cost(response.usage)
        total_cost += cost

        messages.append({"role": "assistant", "content": response.content})

        for block in response.content:
            if block.type == "text":
                print(f"[Worker-{WORKER_ID}] {block.text[:500]}")

        # Collect any tool_use blocks regardless of stop_reason
        # (handles both "tool_use" and "max_tokens" truncation)
        tool_use_blocks = [b for b in response.content if b.type == "tool_use"]

        if not tool_use_blocks:
            # No tools called — worker is done or hit max_tokens with only text
            if response.stop_reason == "max_tokens":
                print(f"[Worker-{WORKER_ID}] Hit max_tokens, continuing...")
                messages.append({"role": "user", "content": "Continue from where you left off."})
                continue
            print(f"[Worker-{WORKER_ID}] Done. Cost: ${total_cost:.4f}")
            break

        # Process all tool calls
        tool_results = []
        for block in tool_use_blocks:
            print(f"[Worker-{WORKER_ID}] Tool: {block.name}")
            try:
                result = handle_tool_call(block.name, block.input)
            except Exception as e:
                result = f"Tool error: {type(e).__name__}: {e}"
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": result,
            })
        messages.append({"role": "user", "content": tool_results})

    # Log completion
    log_entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "worker_id": WORKER_ID,
        "role": WORKER_ROLE,
        "task_id": task_id,
        "cost_usd": round(total_cost, 4),
        "iterations": iteration + 1,
    }
    log_path = BASE_DIR / "logs" / f"workers_{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.jsonl"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with open(log_path, "a") as f:
        f.write(json.dumps(log_entry) + "\n")


def write_error_result(task_id: str, error: str):
    result = {
        "task_id": task_id,
        "status": "failed",
        "summary": "Worker encountered an error",
        "error": error,
    }
    result_path = RESULTS_DIR / f"{task_id}.json"
    result_path.parent.mkdir(parents=True, exist_ok=True)
    result_path.write_text(json.dumps(result, indent=2))


if __name__ == "__main__":
    run_worker()
