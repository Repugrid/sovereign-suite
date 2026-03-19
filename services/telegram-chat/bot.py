#!/usr/bin/env python3
"""
Sovereign Telegram Chat — Free Claude chat with full Sovereign context.
Commands (/) route to n8n. Everything else goes to Claude.
"""

import json
import os
import time
import logging
import sqlite3
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

import anthropic

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("tg-chat")

# ── Config ──────────────────────────────────────────────────────────────
TG_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
TG_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")
ANTHROPIC_API_KEY = os.environ["ANTHROPIC_API_KEY"]
N8N_WEBHOOK = os.environ.get("N8N_WEBHOOK", "http://n8n:5678/webhook/telegram-commands")
NODEWATCH_API = os.environ.get("NODEWATCH_API", "http://sovereign-nodewatch-api:9081")
SHARED_DIR = Path(os.environ.get("SHARED_DIR", "/data/shared"))
MODEL = os.environ.get("CHAT_MODEL", "claude-sonnet-4-20250514")
MAX_HISTORY = 20  # messages per conversation

TG_API = f"https://api.telegram.org/bot{TG_TOKEN}"

# Known n8n commands
N8N_COMMANDS = {"/status", "/top", "/learning", "/stop", "/start", "/help"}

# ── Conversation Store (SQLite) ─────────────────────────────────────────
DB_PATH = "/data/chat.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            chat_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            ts DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("CREATE INDEX IF NOT EXISTS idx_chat ON messages(chat_id, ts)")
    conn.commit()
    conn.close()


def save_message(chat_id: int, role: str, content: str):
    conn = sqlite3.connect(DB_PATH)
    conn.execute("INSERT INTO messages (chat_id, role, content) VALUES (?, ?, ?)",
                 (chat_id, role, content))
    # Keep only last MAX_HISTORY*2 messages per chat
    conn.execute("""
        DELETE FROM messages WHERE chat_id = ? AND id NOT IN (
            SELECT id FROM messages WHERE chat_id = ? ORDER BY ts DESC LIMIT ?
        )
    """, (chat_id, chat_id, MAX_HISTORY * 2))
    conn.commit()
    conn.close()


def get_history(chat_id: int) -> list[dict]:
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        "SELECT role, content FROM messages WHERE chat_id = ? ORDER BY ts ASC",
        (chat_id,)
    ).fetchall()
    conn.close()
    return [{"role": r[0], "content": r[1]} for r in rows]


# ── Telegram Helpers ────────────────────────────────────────────────────
def tg_request(method: str, data: dict) -> dict:
    payload = json.dumps(data).encode()
    req = urllib.request.Request(
        f"{TG_API}/{method}",
        data=payload,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read())


def tg_send(chat_id: int, text: str):
    """Send message, splitting if too long."""
    # Telegram max is 4096 chars
    chunks = [text[i:i+4000] for i in range(0, len(text), 4000)]
    for chunk in chunks:
        try:
            tg_request("sendMessage", {
                "chat_id": chat_id,
                "text": chunk,
                "parse_mode": "Markdown",
            })
        except Exception:
            # Fallback without markdown if it fails
            try:
                tg_request("sendMessage", {
                    "chat_id": chat_id,
                    "text": chunk,
                })
            except Exception as e:
                log.error(f"Failed to send message: {e}")


def tg_send_typing(chat_id: int):
    try:
        tg_request("sendChatAction", {"chat_id": chat_id, "action": "typing"})
    except Exception:
        pass


# ── Context Gathering ───────────────────────────────────────────────────
def get_sovereign_context() -> str:
    """Gather live context from Sovereign infrastructure."""
    parts = []

    # Server metrics
    try:
        req = urllib.request.Request(f"{NODEWATCH_API}/api/v1/servers", headers={"User-Agent": "TG-Chat/1.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            servers = json.loads(resp.read())
        parts.append(f"**Node-Watch:** {len(servers.get('servers', []))} server(s) reporting")
        for srv in servers.get("servers", []):
            try:
                req2 = urllib.request.Request(
                    f"{NODEWATCH_API}/api/v1/servers/{srv['server_id']}/status",
                    headers={"User-Agent": "TG-Chat/1.0"})
                with urllib.request.urlopen(req2, timeout=5) as resp2:
                    status = json.loads(resp2.read())
                parts.append(
                    f"  - {status.get('hostname', '?')}: {status.get('status', '?')} "
                    f"(CPU {status.get('cpu_percent', '?')}%, RAM {status.get('memory_percent', '?')}%, "
                    f"Disk {status.get('disk_percent', '?')}%)"
                )
            except Exception:
                pass
    except Exception:
        parts.append("**Node-Watch API:** not reachable")

    # Recent CEO activity
    log_dir = SHARED_DIR / "results"
    if log_dir.exists():
        recent = sorted(log_dir.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True)[:5]
        parts.append(f"\n**Recent files ({len(recent)}):** " + ", ".join(p.name for p in recent))

    # P&L
    pnl_path = SHARED_DIR / "results" / "pnl.md"
    if pnl_path.exists():
        parts.append(f"\n**P&L:**\n{pnl_path.read_text()[:500]}")

    # Email stats
    email_log = Path("/data/logs/emails_sent.jsonl")
    if email_log.exists():
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        lines = email_log.read_text().strip().split("\n")
        today_count = sum(1 for l in lines if today in l)
        parts.append(f"\n**Emails:** {today_count}/10 sent today, {len(lines)} total")

    return "\n".join(parts)


SYSTEM_PROMPT = """Du bist der Sovereign CEO Assistant — ein KI-Assistent der uber Telegram mit dem Board of Directors kommuniziert.

Du hast Zugriff auf:
- Echtzeit-Serverdaten von Node-Watch (Monitoring-Produkt)
- CEO-Agent Aktivitaten und Logs
- P&L Tracking
- Email-Outreach-Status

Antworte knapp und direkt. Nutze Emojis sparsam. Wenn du nach Daten gefragt wirst, gib echte Zahlen aus dem Kontext.

Sprache: Antworte in der Sprache in der du angesprochen wirst (deutsch/englisch).

Du bist KEIN generischer Chatbot. Du bist der direkte Draht zum Sovereign-System. Wenn jemand fragt "was passiert gerade", gib den echten Status.

Aktuelle Live-Daten:
{context}

Datum: {date}
"""


# ── Claude Chat ─────────────────────────────────────────────────────────
def chat_with_claude(chat_id: int, user_message: str) -> str:
    """Send message to Claude with Sovereign context and conversation history."""
    client = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)

    context = get_sovereign_context()
    system = SYSTEM_PROMPT.format(
        context=context,
        date=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
    )

    # Get conversation history
    history = get_history(chat_id)

    # Add current message
    messages = history + [{"role": "user", "content": user_message}]

    try:
        response = client.messages.create(
            model=MODEL,
            max_tokens=2000,
            system=system,
            messages=messages,
        )
        reply = response.content[0].text
        return reply
    except Exception as e:
        log.error(f"Claude API error: {e}")
        return f"Fehler bei Claude API: {e}"


# ── N8N Forward ─────────────────────────────────────────────────────────
def forward_to_n8n(update: dict):
    """Forward a command to the n8n Telegram webhook."""
    try:
        payload = json.dumps(update).encode()
        req = urllib.request.Request(
            N8N_WEBHOOK,
            data=payload,
            headers={"Content-Type": "application/json"},
        )
        urllib.request.urlopen(req, timeout=10)
        log.info("Forwarded command to n8n")
    except Exception as e:
        log.error(f"n8n forward failed: {e}")


# ── Main Loop (Long Polling) ───────────────────────────────────────────
def run():
    init_db()

    # Remove webhook so we can use polling
    # We'll set up a proxy approach instead: keep webhook for n8n,
    # but since we need polling for chat, we switch to polling mode
    # and forward commands to n8n via HTTP
    log.info("Removing Telegram webhook for polling mode...")
    tg_request("deleteWebhook", {"drop_pending_updates": False})
    time.sleep(1)

    log.info("Sovereign Telegram Chat started (polling mode)")
    tg_send(int(TG_CHAT_ID), "🟢 *Sovereign Chat online*\nSchreib mir was — ich hab Zugriff auf alle Sovereign-Daten.")

    offset = 0
    while True:
        try:
            updates = tg_request("getUpdates", {
                "offset": offset,
                "timeout": 30,
                "allowed_updates": ["message"],
            })

            for update in updates.get("result", []):
                offset = update["update_id"] + 1
                msg = update.get("message", {})
                chat_id = msg.get("chat", {}).get("id")
                text = msg.get("text", "").strip()

                if not chat_id or not text:
                    continue

                # Auth check: only respond to authorized chat
                if TG_CHAT_ID and str(chat_id) != TG_CHAT_ID:
                    tg_send(chat_id, "Unauthorized.")
                    continue

                log.info(f"Message from {chat_id}: {text[:80]}")

                # Route commands to n8n
                cmd = text.split()[0].lower() if text.startswith("/") else ""
                if cmd in N8N_COMMANDS:
                    log.info(f"Routing {cmd} to n8n")
                    forward_to_n8n(update)
                    continue

                # Special commands for this bot
                if cmd == "/clear":
                    conn = sqlite3.connect(DB_PATH)
                    conn.execute("DELETE FROM messages WHERE chat_id = ?", (chat_id,))
                    conn.commit()
                    conn.close()
                    tg_send(chat_id, "Konversation geloescht.")
                    continue

                if cmd == "/servers":
                    ctx = get_sovereign_context()
                    tg_send(chat_id, ctx)
                    continue

                # Claude chat
                tg_send_typing(chat_id)
                save_message(chat_id, "user", text)

                reply = chat_with_claude(chat_id, text)

                save_message(chat_id, "assistant", reply)
                tg_send(chat_id, reply)

        except urllib.error.URLError as e:
            log.warning(f"Polling error: {e}")
            time.sleep(5)
        except Exception as e:
            log.error(f"Unexpected error: {e}")
            time.sleep(5)


if __name__ == "__main__":
    run()
