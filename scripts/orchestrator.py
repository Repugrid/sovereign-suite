#!/usr/bin/env python3
"""
Project Sovereign — CEO Agent Orchestrator
Launches the CEO agent with MCP tools, manages budget, logs decisions.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import anthropic
from dotenv import load_dotenv

# Import spawner for delegation
sys.path.insert(0, str(Path(__file__).parent))
from spawner import spawn_worker, spawn_batch, check_worker, check_task_result, list_active_workers, kill_worker

# ── Config ──────────────────────────────────────────────────────────────
load_dotenv()

MODEL = "claude-sonnet-4-20250514"
MAX_TOKENS = 8096
LOG_DIR = Path("/root/sovereign/logs")
SHARED_DIR = Path("/root/sovereign/shared")
AGENT_DIR = Path("/root/sovereign/agents")
DAILY_BUDGET = float(os.getenv("DAILY_API_BUDGET_USD", "50.00"))
ALERT_PCT = float(os.getenv("ALERT_THRESHOLD_PCT", "80")) / 100

# ── Pricing (per 1M tokens, USD) ───────────────────────────────────────
PRICING = {
    "input": 3.00,
    "output": 15.00,
    "cache_read": 0.30,
    "cache_write": 3.75,
}

# ── State ───────────────────────────────────────────────────────────────
daily_cost_usd = 0.0
session_start = datetime.now(timezone.utc)


def estimate_cost(usage: anthropic.types.Usage) -> float:
    """Calculate cost from API usage object."""
    input_cost = (usage.input_tokens / 1_000_000) * PRICING["input"]
    output_cost = (usage.output_tokens / 1_000_000) * PRICING["output"]
    cache_read = getattr(usage, "cache_read_input_tokens", 0) or 0
    cache_write = getattr(usage, "cache_creation_input_tokens", 0) or 0
    cache_cost = (cache_read / 1_000_000) * PRICING["cache_read"] + \
                 (cache_write / 1_000_000) * PRICING["cache_write"]
    return input_cost + output_cost + cache_cost


def log_event(event_type: str, data: dict):
    """Append structured log entry."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOG_DIR / f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}.jsonl"
    entry = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "type": event_type,
        **data,
    }
    with open(log_file, "a") as f:
        f.write(json.dumps(entry) + "\n")


def load_system_prompt() -> str:
    """Load CEO system prompt from file."""
    prompt_path = AGENT_DIR / "ceo_system_prompt.md"
    return prompt_path.read_text()


def build_mcp_tools() -> list[dict]:
    """
    Define tools the CEO agent can use.
    These map to MCP server capabilities (filesystem + fetch).
    """
    return [
        {
            "name": "read_file",
            "description": "Read a file from the shared workspace or logs directory.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to /root/sovereign/ (e.g. shared/tasks.json)"
                    }
                },
                "required": ["path"],
            },
        },
        {
            "name": "write_file",
            "description": "Write content to a file in the shared workspace.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "File path relative to /root/sovereign/shared/"
                    },
                    "content": {
                        "type": "string",
                        "description": "Content to write"
                    }
                },
                "required": ["path", "content"],
            },
        },
        {
            "name": "list_files",
            "description": "List files in a directory within the shared workspace.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "directory": {
                        "type": "string",
                        "description": "Directory path relative to /root/sovereign/"
                    }
                },
                "required": ["directory"],
            },
        },
        {
            "name": "fetch_url",
            "description": "Make an HTTP GET request to fetch data from a URL.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to fetch"
                    }
                },
                "required": ["url"],
            },
        },
        {
            "name": "get_budget_status",
            "description": "Check current API spend and remaining daily budget.",
            "input_schema": {
                "type": "object",
                "properties": {},
            },
        },
        # ── Delegation Tools ────────────────────────────────────────
        {
            "name": "delegate_task",
            "description": "Spawn a worker agent in a new container to handle a specific task. Roles: coder, marketer, researcher. The worker will read its task, execute it, and write results to shared/results/.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "role": {
                        "type": "string",
                        "enum": ["coder", "marketer", "researcher"],
                        "description": "The type of worker to spawn"
                    },
                    "task_id": {
                        "type": "string",
                        "description": "Unique task ID (e.g. marketing_email_001)"
                    },
                    "instruction": {
                        "type": "string",
                        "description": "Detailed instruction for the worker"
                    },
                    "context": {
                        "type": "object",
                        "description": "Additional context (target market, language, etc.)"
                    }
                },
                "required": ["role", "task_id", "instruction"],
            },
        },
        {
            "name": "delegate_batch",
            "description": "Spawn multiple workers of the same role for parallel execution.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "role": {
                        "type": "string",
                        "enum": ["coder", "marketer", "researcher"],
                    },
                    "tasks": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "task_id": {"type": "string"},
                                "instruction": {"type": "string"},
                                "context": {"type": "object"},
                            },
                            "required": ["instruction"],
                        },
                        "description": "List of tasks to delegate"
                    }
                },
                "required": ["role", "tasks"],
            },
        },
        {
            "name": "check_task",
            "description": "Check if a delegated task has been completed and get its result.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "The task ID to check"
                    }
                },
                "required": ["task_id"],
            },
        },
        {
            "name": "list_workers",
            "description": "List all currently running worker containers.",
            "input_schema": {
                "type": "object",
                "properties": {},
            },
        },
        {
            "name": "kill_worker",
            "description": "Force stop a misbehaving or stuck worker container.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "container_name": {
                        "type": "string",
                        "description": "Container name to kill (e.g. sovereign-worker_coder_abc123)"
                    }
                },
                "required": ["container_name"],
            },
        },
        # ── Deployment Tools ─────────────────────────────────────────
        {
            "name": "deploy_static_site",
            "description": "Deploy a static HTML site to the Sovereign web server. The site will be accessible at http://<server-ip>:9080/<project_name>/. Write the HTML content and provide the project name.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "project_name": {
                        "type": "string",
                        "description": "URL-safe project name (e.g. node-watch). Creates /deployments/<project_name>/index.html"
                    },
                    "html_content": {
                        "type": "string",
                        "description": "Complete HTML content for the landing page (include all CSS inline or via CDN)"
                    }
                },
                "required": ["project_name", "html_content"],
            },
        },
        {
            "name": "list_deployments",
            "description": "List all deployed static sites on the Sovereign web server.",
            "input_schema": {
                "type": "object",
                "properties": {},
            },
        },
        # ── Email Tools ──────────────────────────────────────────────
        {
            "name": "send_email",
            "description": "Send a professional email via Postmark from hello@repugrid.com. Use for outreach, partnerships, and customer communication. RULES: 1) Never spam — only send to relevant businesses. 2) Max 10 emails per day. 3) Always include unsubscribe option. 4) Log every email sent.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "to": {
                        "type": "string",
                        "description": "Recipient email address"
                    },
                    "subject": {
                        "type": "string",
                        "description": "Email subject line"
                    },
                    "html_body": {
                        "type": "string",
                        "description": "HTML email body"
                    },
                    "text_body": {
                        "type": "string",
                        "description": "Plain text fallback"
                    }
                },
                "required": ["to", "subject", "text_body"],
            },
        },
        {
            "name": "get_email_stats",
            "description": "Check how many emails were sent today and delivery stats.",
            "input_schema": {
                "type": "object",
                "properties": {},
            },
        },
    ]


def handle_tool_call(tool_name: str, tool_input: dict) -> str:
    """Execute a tool call and return the result."""
    global daily_cost_usd
    base = Path("/root/sovereign")

    if tool_name == "read_file":
        target = base / tool_input["path"]
        if not target.exists():
            return f"Error: File not found: {tool_input['path']}"
        return target.read_text()[:50_000]  # cap read size

    elif tool_name == "write_file":
        target = base / "shared" / tool_input["path"]
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(tool_input["content"])
        return f"OK: Written {len(tool_input['content'])} bytes to {target}"

    elif tool_name == "list_files":
        target = base / tool_input["directory"]
        if not target.is_dir():
            return f"Error: Not a directory: {tool_input['directory']}"
        files = sorted(str(p.relative_to(base)) for p in target.rglob("*") if p.is_file())
        return json.dumps(files[:200])

    elif tool_name == "fetch_url":
        import urllib.request
        try:
            req = urllib.request.Request(
                tool_input["url"],
                headers={"User-Agent": "Sovereign-CEO/1.0"}
            )
            with urllib.request.urlopen(req, timeout=30) as resp:
                return resp.read().decode("utf-8", errors="replace")[:50_000]
        except Exception as e:
            return f"Fetch error: {e}"

    elif tool_name == "get_budget_status":
        return json.dumps({
            "daily_budget_usd": DAILY_BUDGET,
            "spent_usd": round(daily_cost_usd, 4),
            "remaining_usd": round(DAILY_BUDGET - daily_cost_usd, 4),
            "utilization_pct": round((daily_cost_usd / DAILY_BUDGET) * 100, 1),
            "session_start": session_start.isoformat(),
        })

    # ── Delegation Tools ────────────────────────────────────────────
    elif tool_name == "delegate_task":
        result = spawn_worker(
            role=tool_input["role"],
            task_id=tool_input["task_id"],
            instruction=tool_input["instruction"],
            context=tool_input.get("context"),
        )
        return json.dumps(result)

    elif tool_name == "delegate_batch":
        results = spawn_batch(
            role=tool_input["role"],
            tasks=tool_input["tasks"],
        )
        return json.dumps(results)

    elif tool_name == "check_task":
        result = check_task_result(tool_input["task_id"])
        if result:
            return json.dumps(result)
        return json.dumps({"status": "pending", "message": "Task not yet completed. Worker may still be running."})

    elif tool_name == "list_workers":
        workers = list_active_workers()
        return json.dumps({"active_workers": workers, "count": len(workers)})

    elif tool_name == "kill_worker":
        status = kill_worker(tool_input["container_name"])
        return json.dumps({"container": tool_input["container_name"], "result": status})

    # ── Deployment Tools ────────────────────────────────────────────
    elif tool_name == "deploy_static_site":
        deploy_dir = Path("/root/sovereign/deployments") / tool_input["project_name"]
        deploy_dir.mkdir(parents=True, exist_ok=True)
        index_path = deploy_dir / "index.html"
        index_path.write_text(tool_input["html_content"])
        server_ip = os.getenv("SERVER_IP", "localhost")
        url = f"http://{server_ip}:9080/{tool_input['project_name']}/"
        log_event("deployment", {
            "project": tool_input["project_name"],
            "url": url,
            "size_bytes": len(tool_input["html_content"]),
        })
        return json.dumps({
            "status": "deployed",
            "url": url,
            "path": str(index_path),
            "size_bytes": len(tool_input["html_content"]),
        })

    elif tool_name == "list_deployments":
        deploy_base = Path("/root/sovereign/deployments")
        if not deploy_base.exists():
            return json.dumps({"deployments": [], "count": 0})
        projects = []
        server_ip = os.getenv("SERVER_IP", "localhost")
        for d in sorted(deploy_base.iterdir()):
            if d.is_dir() and (d / "index.html").exists():
                size = (d / "index.html").stat().st_size
                projects.append({
                    "name": d.name,
                    "url": f"http://{server_ip}:9080/{d.name}/",
                    "size_bytes": size,
                })
        return json.dumps({"deployments": projects, "count": len(projects)})

    # ── Email Tools ────────────────────────────────────────────────
    elif tool_name == "send_email":
        import urllib.request
        postmark_token = os.getenv("POSTMARK_SERVER_TOKEN", "")
        if not postmark_token:
            return json.dumps({"error": "POSTMARK_SERVER_TOKEN not configured"})

        # Daily limit check
        email_log = Path("/root/sovereign/logs/emails_sent.jsonl")
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        sent_today = 0
        if email_log.exists():
            for line in email_log.read_text().strip().split("\n"):
                if line and today in line:
                    sent_today += 1
        if sent_today >= 10:
            return json.dumps({"error": "Daily email limit reached (10/day)", "sent_today": sent_today})

        payload = json.dumps({
            "From": "hello@repugrid.com",
            "To": tool_input["to"],
            "Subject": tool_input["subject"],
            "TextBody": tool_input["text_body"],
            "HtmlBody": tool_input.get("html_body", ""),
            "MessageStream": "outbound",
        }).encode()

        req = urllib.request.Request(
            "https://api.postmarkapp.com/email",
            data=payload,
            headers={
                "X-Postmark-Server-Token": postmark_token,
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read().decode())
            # Log the send
            email_log.parent.mkdir(parents=True, exist_ok=True)
            with open(email_log, "a") as f:
                f.write(json.dumps({
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "to": tool_input["to"],
                    "subject": tool_input["subject"],
                    "message_id": result.get("MessageID", ""),
                    "status": "sent",
                }) + "\n")
            log_event("email_sent", {"to": tool_input["to"], "subject": tool_input["subject"]})
            return json.dumps({"status": "sent", "message_id": result.get("MessageID"), "sent_today": sent_today + 1})
        except Exception as e:
            return json.dumps({"error": f"Email send failed: {e}"})

    elif tool_name == "get_email_stats":
        email_log = Path("/root/sovereign/logs/emails_sent.jsonl")
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        sent_today = 0
        total = 0
        if email_log.exists():
            for line in email_log.read_text().strip().split("\n"):
                if line:
                    total += 1
                    if today in line:
                        sent_today += 1
        return json.dumps({"sent_today": sent_today, "daily_limit": 10, "total_all_time": total})

    return f"Unknown tool: {tool_name}"


def run_ceo_loop():
    """Main agentic loop — CEO thinks, uses tools, repeats."""
    global daily_cost_usd

    client = anthropic.Anthropic()
    system_prompt = load_system_prompt()
    tools = build_mcp_tools()

    print(f"[Sovereign] CEO Agent starting — budget: ${DAILY_BUDGET}/day")
    print(f"[Sovereign] Model: {MODEL}")
    log_event("startup", {"model": MODEL, "budget": DAILY_BUDGET})

    messages = [
        {
            "role": "user",
            "content": (
                "You are now online. Check your available tools, review the shared workspace, "
                "and report your status. Then identify the highest-ROI task you can execute right now "
                "for our business units (RepuGrid & Praxis-Reputation)."
            ),
        }
    ]

    while True:
        # Budget check
        if daily_cost_usd >= DAILY_BUDGET:
            log_event("budget_exceeded", {"spent": daily_cost_usd})
            print(f"[Sovereign] BUDGET EXCEEDED (${daily_cost_usd:.2f}). Shutting down.")
            break

        try:
            response = client.messages.create(
                model=MODEL,
                max_tokens=MAX_TOKENS,
                system=[{"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}],
                tools=tools,
                messages=messages,
            )
        except anthropic.APIError as e:
            log_event("api_error", {"error": str(e)})
            print(f"[Sovereign] API Error: {e}. Retrying in 60s...")
            time.sleep(60)
            continue

        # Track cost
        cost = estimate_cost(response.usage)
        daily_cost_usd += cost
        log_event("api_call", {
            "cost_usd": round(cost, 4),
            "total_usd": round(daily_cost_usd, 4),
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "stop_reason": response.stop_reason,
        })

        if daily_cost_usd / DAILY_BUDGET >= ALERT_PCT:
            print(f"[Sovereign] WARNING: Budget at {(daily_cost_usd/DAILY_BUDGET)*100:.0f}%")

        # Process response
        assistant_content = response.content
        messages.append({"role": "assistant", "content": assistant_content})

        # Print text blocks
        for block in assistant_content:
            if block.type == "text":
                print(f"\n[CEO] {block.text}\n")
                log_event("ceo_output", {"text": block.text[:2000]})

        # If no tool use, the CEO is done thinking for this cycle
        if response.stop_reason == "end_turn":
            log_event("cycle_complete", {"cost_total": round(daily_cost_usd, 4)})
            print(f"[Sovereign] Cycle complete. Spent: ${daily_cost_usd:.4f}")
            # Wait before next autonomous cycle
            time.sleep(300)  # 5 min between autonomous cycles
            messages.append({
                "role": "user",
                "content": (
                    "5 minutes have passed. Check budget status, review any updates in "
                    "the shared workspace, and decide on your next action."
                ),
            })
            continue

        # Handle tool calls
        if response.stop_reason == "tool_use":
            tool_results = []
            for block in assistant_content:
                if block.type == "tool_use":
                    print(f"[Tool] {block.name}({json.dumps(block.input)[:200]})")
                    try:
                        result = handle_tool_call(block.name, block.input)
                    except Exception as e:
                        result = f"Tool error: {type(e).__name__}: {e}"
                        print(f"[Tool Error] {block.name}: {result}")
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })
                    log_event("tool_call", {
                        "tool": block.name,
                        "input": block.input,
                        "result_length": len(result),
                    })
            messages.append({"role": "user", "content": tool_results})


def main():
    """Entry point with error handling."""
    try:
        run_ceo_loop()
    except KeyboardInterrupt:
        print("\n[Sovereign] Manual shutdown.")
        log_event("shutdown", {"reason": "keyboard_interrupt"})
    except Exception as e:
        log_event("fatal_error", {"error": str(e)})
        print(f"[Sovereign] Fatal: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
