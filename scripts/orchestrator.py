#!/usr/bin/env python3
"""
Project Sovereign — CEO Agent Orchestrator
Launches the CEO agent with MCP tools, manages budget, logs decisions.
"""

import json
import os
import sys
import time
import uuid
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

# ── Telegram ────────────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")


def telegram_send(text: str, parse_mode: str = "Markdown") -> bool:
    """Send a Telegram message to the Board. Silent on failure."""
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return False
    import urllib.request
    try:
        payload = json.dumps({
            "chat_id": TELEGRAM_CHAT_ID,
            "text": text[:4000],
            "parse_mode": parse_mode,
        }).encode()
        req = urllib.request.Request(
            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage",
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
        return True
    except Exception:
        return False


# ── State ───────────────────────────────────────────────────────────────
BUDGET_FILE = Path("/root/sovereign/shared/.budget_spent_today.json")
daily_cost_usd = 0.0
session_start = datetime.now(timezone.utc)
task_check_counts: dict[str, int] = {}  # Track how many times each task was polled


def _load_persisted_budget() -> float:
    """Load today's spend from disk. Returns 0.0 if file missing or stale."""
    try:
        data = json.loads(BUDGET_FILE.read_text())
        if data.get("date") == datetime.now(timezone.utc).strftime("%Y-%m-%d"):
            return float(data.get("spent_usd", 0.0))
    except (FileNotFoundError, json.JSONDecodeError, KeyError):
        pass
    return 0.0


def _persist_budget(spent: float):
    """Write today's cumulative spend to disk."""
    BUDGET_FILE.write_text(json.dumps({
        "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "spent_usd": round(spent, 4),
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }))


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
        # ── GitHub Tools ─────────────────────────────────────────────
        {
            "name": "github_create_discussion",
            "description": "Create a GitHub Discussion in the sovereign-suite repo. Use for announcements, show & tell, and community engagement. Category must be one of: Announcements, General, Ideas, Q&A, Show and tell.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Discussion title"},
                    "body": {"type": "string", "description": "Discussion body (Markdown)"},
                    "category": {"type": "string", "description": "Category: Announcements, General, Ideas, Q&A, Show and tell"},
                },
                "required": ["title", "body", "category"],
            },
        },
        {
            "name": "github_create_release",
            "description": "Create a GitHub Release with a tag. Use for version milestones.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "tag": {"type": "string", "description": "Version tag (e.g. v0.1.0)"},
                    "name": {"type": "string", "description": "Release title"},
                    "body": {"type": "string", "description": "Release notes (Markdown)"},
                },
                "required": ["tag", "name", "body"],
            },
        },
        {
            "name": "github_post_comment",
            "description": "Post a comment on a GitHub issue or discussion.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "issue_number": {"type": "integer", "description": "Issue or PR number"},
                    "body": {"type": "string", "description": "Comment body (Markdown)"},
                },
                "required": ["issue_number", "body"],
            },
        },
        {
            "name": "github_create_issue",
            "description": "Create a GitHub Issue in the sovereign-suite repo.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "title": {"type": "string", "description": "Issue title"},
                    "body": {"type": "string", "description": "Issue body (Markdown)"},
                    "labels": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Labels (e.g. ['good first issue', 'help wanted'])",
                    },
                },
                "required": ["title", "body"],
            },
        },
        {
            "name": "post_tweet",
            "description": "Post a tweet to X/Twitter from the Sovereign account. Max 280 characters. Use for announcements, milestones, and engagement. Do NOT spam — max 5 tweets per day.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "text": {"type": "string", "description": "Tweet text (max 280 chars)"},
                },
                "required": ["text"],
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
        if "error" not in result:
            telegram_send("🔧 *Worker spawned:* %s\nTask: `%s`" % (tool_input["role"], tool_input["task_id"]))
        return json.dumps(result)

    elif tool_name == "delegate_batch":
        results = spawn_batch(
            role=tool_input["role"],
            tasks=tool_input["tasks"],
        )
        return json.dumps(results)

    elif tool_name == "check_task":
        tid = tool_input["task_id"]
        result = check_task_result(tid)
        if result:
            task_check_counts.pop(tid, None)
            return json.dumps(result)
        # Anti-polling: max 3 checks per task, then tell CEO to move on
        task_check_counts[tid] = task_check_counts.get(tid, 0) + 1
        if task_check_counts[tid] > 3:
            return json.dumps({
                "status": "timeout",
                "message": f"Task '{tid}' checked {task_check_counts[tid]} times with no result. "
                           "The worker likely failed or is stuck. STOP polling this task. "
                           "Move on to the next action from your directive. "
                           "If the task is critical, spawn a NEW worker with a simpler instruction."
            })

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
            telegram_send("📧 *Email sent:* %s\nTo: `%s`\n(%d/10 today)" % (
                tool_input["subject"], tool_input["to"], sent_today + 1))
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

    # ── GitHub Tools ────────────────────────────────────────────
    elif tool_name in ("github_create_discussion", "github_create_release", "github_post_comment"):
        import urllib.request as urllib2
        gh_token = os.getenv("GITHUB_TOKEN", "")
        gh_repo = os.getenv("GITHUB_REPO", "Repugrid/sovereign-suite")
        if not gh_token:
            return json.dumps({"error": "GITHUB_TOKEN not configured"})

        gh_headers = {
            "Authorization": f"token {gh_token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
        }

        try:
            if tool_name == "github_create_release":
                payload = json.dumps({
                    "tag_name": tool_input["tag"],
                    "name": tool_input["name"],
                    "body": tool_input["body"],
                    "draft": False,
                    "prerelease": "alpha" in tool_input["tag"] or "beta" in tool_input["tag"],
                }).encode()
                req = urllib2.Request(
                    f"https://api.github.com/repos/{gh_repo}/releases",
                    data=payload, headers=gh_headers,
                )
                with urllib2.urlopen(req, timeout=15) as resp:
                    result = json.loads(resp.read())
                telegram_send("📦 *GitHub Release:* %s\n%s" % (tool_input["name"], result.get("html_url", "")))
                return json.dumps({"status": "created", "url": result.get("html_url"), "id": result.get("id")})

            elif tool_name == "github_create_discussion":
                # Discussions require GraphQL API
                # First get repo ID and category ID
                query = '''query { repository(owner:"%s", name:"%s") {
                    id
                    discussionCategories(first:10) { nodes { id name } }
                }}''' % tuple(gh_repo.split("/"))
                req = urllib2.Request(
                    "https://api.github.com/graphql",
                    data=json.dumps({"query": query}).encode(),
                    headers=gh_headers,
                )
                with urllib2.urlopen(req, timeout=15) as resp:
                    gql = json.loads(resp.read())

                repo_data = gql.get("data", {}).get("repository", {})
                repo_id = repo_data.get("id")
                categories = {c["name"]: c["id"] for c in repo_data.get("discussionCategories", {}).get("nodes", [])}
                cat_id = categories.get(tool_input["category"])

                if not cat_id:
                    return json.dumps({"error": f"Category '{tool_input['category']}' not found. Available: {list(categories.keys())}"})

                mutation = '''mutation {
                    createDiscussion(input: {repositoryId: "%s", categoryId: "%s", title: "%s", body: "%s"}) {
                        discussion { url number }
                    }
                }''' % (repo_id, cat_id, tool_input["title"].replace('"', '\\"'), tool_input["body"].replace('"', '\\"').replace("\n", "\\n"))
                req = urllib2.Request(
                    "https://api.github.com/graphql",
                    data=json.dumps({"query": mutation}).encode(),
                    headers=gh_headers,
                )
                with urllib2.urlopen(req, timeout=15) as resp:
                    result = json.loads(resp.read())
                disc = result.get("data", {}).get("createDiscussion", {}).get("discussion", {})
                telegram_send("💬 *GitHub Discussion:* %s\n%s" % (tool_input["title"], disc.get("url", "")))
                return json.dumps({"status": "created", "url": disc.get("url"), "number": disc.get("number")})

            elif tool_name == "github_post_comment":
                payload = json.dumps({"body": tool_input["body"]}).encode()
                req = urllib2.Request(
                    f"https://api.github.com/repos/{gh_repo}/issues/{tool_input['issue_number']}/comments",
                    data=payload, headers=gh_headers,
                )
                with urllib2.urlopen(req, timeout=15) as resp:
                    result = json.loads(resp.read())
                return json.dumps({"status": "created", "url": result.get("html_url"), "id": result.get("id")})

        except Exception as e:
            return json.dumps({"error": f"GitHub API failed: {e}"})

    elif tool_name == "github_create_issue":
        import urllib.request as urllib2
        gh_token = os.getenv("GITHUB_TOKEN", "")
        gh_repo = os.getenv("GITHUB_REPO", "Repugrid/sovereign-suite")
        if not gh_token:
            return json.dumps({"error": "GITHUB_TOKEN not configured"})
        try:
            payload_data = {
                "title": tool_input["title"],
                "body": tool_input["body"],
            }
            if tool_input.get("labels"):
                payload_data["labels"] = tool_input["labels"]
            payload = json.dumps(payload_data).encode()
            req = urllib2.Request(
                f"https://api.github.com/repos/{gh_repo}/issues",
                data=payload,
                headers={
                    "Authorization": f"token {gh_token}",
                    "Accept": "application/vnd.github+json",
                    "Content-Type": "application/json",
                },
            )
            with urllib2.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read())
            telegram_send("🐛 *GitHub Issue #%s:* %s\n%s" % (
                result.get("number"), tool_input["title"], result.get("html_url", "")))
            return json.dumps({"status": "created", "url": result.get("html_url"), "number": result.get("number")})
        except Exception as e:
            return json.dumps({"error": f"GitHub Issue creation failed: {e}"})

    elif tool_name == "post_tweet":
        import urllib.request as urllib2
        import hashlib
        import hmac
        import base64
        import urllib.parse

        api_key = os.getenv("TWITTER_API_KEY", "")
        api_secret = os.getenv("TWITTER_API_SECRET", "")
        access_token = os.getenv("TWITTER_ACCESS_TOKEN", "")
        access_secret = os.getenv("TWITTER_ACCESS_TOKEN_SECRET", "")

        if not all([api_key, api_secret, access_token, access_secret]):
            return json.dumps({"error": "Twitter API keys not configured. Set TWITTER_API_KEY, TWITTER_API_SECRET, TWITTER_ACCESS_TOKEN, TWITTER_ACCESS_TOKEN_SECRET in .env"})

        tweet_text = tool_input["text"][:280]

        # Check daily tweet limit
        tweet_log = Path("/root/sovereign/logs/tweets_sent.jsonl")
        tweet_log.parent.mkdir(parents=True, exist_ok=True)
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        tweets_today = 0
        if tweet_log.exists():
            for line in tweet_log.read_text().strip().split("\n"):
                if line and today in line:
                    tweets_today += 1
        if tweets_today >= 5:
            return json.dumps({"error": f"Daily tweet limit reached (5/day). {tweets_today} sent today."})

        try:
            # OAuth 1.0a signature
            import time as _time
            url = "https://api.twitter.com/2/tweets"
            oauth_nonce = uuid.uuid4().hex
            oauth_timestamp = str(int(_time.time()))

            oauth_params = {
                "oauth_consumer_key": api_key,
                "oauth_nonce": oauth_nonce,
                "oauth_signature_method": "HMAC-SHA1",
                "oauth_timestamp": oauth_timestamp,
                "oauth_token": access_token,
                "oauth_version": "1.0",
            }

            # Create signature base string
            param_string = "&".join(f"{urllib.parse.quote(k, safe='')}={urllib.parse.quote(v, safe='')}"
                                     for k, v in sorted(oauth_params.items()))
            base_string = f"POST&{urllib.parse.quote(url, safe='')}&{urllib.parse.quote(param_string, safe='')}"
            signing_key = f"{urllib.parse.quote(api_secret, safe='')}&{urllib.parse.quote(access_secret, safe='')}"
            signature = base64.b64encode(
                hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1).digest()
            ).decode()

            oauth_params["oauth_signature"] = signature
            auth_header = "OAuth " + ", ".join(
                f'{urllib.parse.quote(k, safe="")}="{urllib.parse.quote(v, safe="")}"'
                for k, v in sorted(oauth_params.items())
            )

            payload = json.dumps({"text": tweet_text}).encode()
            req = urllib2.Request(url, data=payload, headers={
                "Authorization": auth_header,
                "Content-Type": "application/json",
            })
            with urllib2.urlopen(req, timeout=15) as resp:
                result = json.loads(resp.read())

            tweet_id = result.get("data", {}).get("id", "unknown")
            tweet_url = f"https://x.com/i/status/{tweet_id}"

            # Log it
            with open(tweet_log, "a") as f:
                f.write(json.dumps({
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "text": tweet_text,
                    "tweet_id": tweet_id,
                }) + "\n")

            telegram_send("🐦 *Tweet posted:*\n%s\n%s" % (tweet_text[:200], tweet_url))
            return json.dumps({"status": "posted", "tweet_id": tweet_id, "url": tweet_url})

        except Exception as e:
            return json.dumps({"error": f"Twitter API failed: {e}"})

    return f"Unknown tool: {tool_name}"


def run_ceo_loop():
    """Main agentic loop — CEO thinks, uses tools, repeats."""
    global daily_cost_usd

    # Restore spend from disk so restarts don't reset the budget
    daily_cost_usd = _load_persisted_budget()
    if daily_cost_usd >= DAILY_BUDGET:
        print(f"[Sovereign] Budget already spent today (${daily_cost_usd:.2f}/${DAILY_BUDGET:.2f}). Exiting.")
        telegram_send("🔴 *CEO restart blocked* — budget already spent ($%.2f/$%.2f)" % (daily_cost_usd, DAILY_BUDGET))
        sys.exit(0)

    client = anthropic.Anthropic()
    system_prompt = load_system_prompt()
    tools = build_mcp_tools()

    print(f"[Sovereign] CEO Agent starting — budget: ${DAILY_BUDGET}/day (already spent: ${daily_cost_usd:.2f})")
    print(f"[Sovereign] Model: {MODEL}")
    log_event("startup", {"model": MODEL, "budget": DAILY_BUDGET})
    telegram_send("🟢 *Sovereign CEO online*\nBudget: $%.2f/day\nModel: %s" % (DAILY_BUDGET, MODEL))

    messages = [
        {
            "role": "user",
            "content": (
                "You are now online. This is a FRESH start — ignore any previous context.\n\n"
                "Step 1: list_files on shared/inbox/ to find your directives.\n"
                "Step 2: Read the directive file (there is exactly ONE active directive).\n"
                "Step 3: Execute it immediately. The directive contains everything you need.\n\n"
                "Do NOT read old master_log.md first. Do NOT check for old tasks. "
                "Read the directive and start building."
            ),
        }
    ]

    while True:
        # Budget check
        if daily_cost_usd >= DAILY_BUDGET:
            log_event("budget_exceeded", {"spent": daily_cost_usd})
            _persist_budget(daily_cost_usd)
            print(f"[Sovereign] BUDGET EXCEEDED (${daily_cost_usd:.2f}). Shutting down.")
            telegram_send("🔴 *Budget exceeded!* $%.2f spent. CEO shutting down." % daily_cost_usd)
            sys.exit(0)  # Exit 0 so Docker doesn't auto-restart

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
        _persist_budget(daily_cost_usd)
        log_event("api_call", {
            "cost_usd": round(cost, 4),
            "total_usd": round(daily_cost_usd, 4),
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens,
            "stop_reason": response.stop_reason,
        })

        if daily_cost_usd / DAILY_BUDGET >= ALERT_PCT:
            print(f"[Sovereign] WARNING: Budget at {(daily_cost_usd/DAILY_BUDGET)*100:.0f}%")
            telegram_send("⚠️ *Budget warning:* $%.2f / $%.2f (%.0f%%)" % (
                daily_cost_usd, DAILY_BUDGET, (daily_cost_usd/DAILY_BUDGET)*100))

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
            time.sleep(120)  # 2 min between autonomous cycles
            messages.append({
                "role": "user",
                "content": (
                    "Next cycle. Check if any delegated workers completed (look in shared/results/ for new files). "
                    "Check budget. Then execute the next concrete step from your active directive. "
                    "Do NOT write summaries. Do NOT enter maintenance mode. Ship code."
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
