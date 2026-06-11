"""Jarvis — the agent's GTD Telegram face: the loop, the NLU, the persona.

This is *reach*, not truth: it parses a human message into an intent (local Ollama), routes
the intent to ``life_agent.tasks`` (the event-sourced commands + read-model), and sends the
reply back over the ``telegram`` transport. "Jarvis" is the persona/voice; the GTD lives in
the brain. Run as the systemd service: ``python -m life_agent.reach.jarvis``.
"""

from __future__ import annotations

import json
import logging
import os
import signal
import sys
import time
from datetime import date
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from life_agent.core import secret
from life_agent.reach import telegram
from life_agent.tasks import commands, store

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("jarvis")

OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3.5:9b")
POLL_TIMEOUT = 30

# The canonical intent vocabulary (docs/interaction-contract.md): one table, three
# renderings — the NLU prompt's "Available actions" block, and the help reply. Each
# entry is (action, JSON schema line for the model, help line for the human). The
# drift gates in tests/test_reach.py assert every action dispatches and appears in
# both renderings, so the table cannot quietly diverge from the behaviour.
INTENTS: tuple[tuple[str, str, str], ...] = (
    ("add",
     '{"action": "add", "text": "task description", "list": "inbox|next|scheduled|someday", "due_date": "YYYY-MM-DD or null"}',
     'Add: "buy milk", "call dentist @health", "schedule report for 2026-05-01"'),
    ("complete",
     '{"action": "complete", "task_id": number_or_null, "text_match": "partial text or null"}',
     'Complete: "done 3" or "done buy milk"'),
    ("delete",
     '{"action": "delete", "task_id": number}',
     'Delete: "delete 5"'),
    ("move",
     '{"action": "move", "task_id": number, "list": "inbox|next|scheduled|someday", "due_date": "YYYY-MM-DD or null"}',
     'Move: "move 5 to next"'),
    ("mark_today",
     '{"action": "mark_today", "task_id": number, "is_today": true|false}',
     'Focus: "today 3" or "focus on 3"; "untoday 3" to unmark'),
    ("clear_today",
     '{"action": "clear_today"}',
     'Clear focus: "clear today"'),
    ("list",
     '{"action": "list", "list": "inbox|next|scheduled|someday|all|today|overdue|null", "tag": "tag_name or null"}',
     'Lists: "show inbox", "show all", "today", "overdue", "show @work"'),
    ("counts",
     '{"action": "counts"}',
     'Counts: "counts" or "stats"'),
    ("completed",
     '{"action": "completed"}',
     'Done this week: "completed"'),
    ("help",
     '{"action": "help"}',
     'Help: "help" or "?"'),
    ("chat",
     '{"action": "chat", "response": "your conversational reply"}',
     "Anything else: I'll just chat"),
)

_ACTIONS_BLOCK = "\n".join(f"- {schema}" for _, schema, _ in INTENTS)

# {today} is substituted by render_prompt's .replace (NOT .format — the schema lines
# carry literal JSON braces). Rules stay hand-written prose: small local models follow
# a few concrete examples better than abstraction.
SYSTEM_PROMPT = f"""You are Jarvis, a GTD (Getting Things Done) task manager assistant. Parse the user's message and return a JSON object with the action to take.

Today's date is {{today}}.

Available actions:
{_ACTIONS_BLOCK}

Rules:
- Default list for new tasks is "inbox" unless the user specifies otherwise.
- If the user says "done", "finished", "completed" followed by a task description, use "complete" with text_match.
- If the user says "done 3" or "complete #3", use "complete" with task_id.
- If the user says "delete 5" or "remove 5", use "delete" with task_id.
- If the user says "show inbox" or "list next", use "list" with the appropriate list name.
- If the user says "show all" or "tasks" or "show tasks", use "list" with list null.
- If the user says "today" or "what's for today", use "list" with list "today".
- If the user says "show @work" or "list @health", use "list" with tag "work" / "health" (the tag without @).
- If the user says "focus on 3" or "today 3", use "mark_today" with is_today true.
- If the user says "schedule X for next tuesday", convert to a date and use "add" with list "scheduled".
- If the user says "move 5 to next", use "move" with the task_id and list.
- For greetings, small talk, or questions not about tasks, use "chat" with a brief friendly response.
- Parse relative dates: "tomorrow" = next day, "next monday" = the coming Monday, etc.
- If ambiguous, prefer "add" to inbox — better to capture than to lose."""


def render_prompt(today: str) -> str:
    """The system prompt with the date substituted. .replace, not .format: the
    schema lines contain literal {} that .format would mangle."""
    return SYSTEM_PROMPT.replace("{today}", today)


def _user_id() -> int:
    """Whose messages the bot accepts — a personal id from env/keyring, never hard-coded."""
    return int(secret("JARVIS_USER_ID"))


def parse_with_ollama(message: str) -> dict[str, Any]:
    prompt = render_prompt(date.today().isoformat())
    body = {
        "model": OLLAMA_MODEL,
        "messages": [
            {"role": "system", "content": prompt},
            {"role": "user", "content": message},
        ],
        "stream": False,
        "format": "json",
    }
    data = json.dumps(body).encode()
    req = Request(
        f"{OLLAMA_URL}/api/chat",  # PII-OK: HTTP endpoint, not a filesystem path
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urlopen(req, timeout=120) as resp:
        result = json.loads(resp.read())
    content = result["message"]["content"]
    parsed: dict[str, Any] = json.loads(content)
    return parsed


def handle_action(parsed: dict[str, Any], user_id: int) -> str:
    """Route a parsed intent to the event-sourced GTD; return the human reply.

    Writes go through ``tasks.commands`` (which append events + fold the read-model); reads
    go through ``tasks.store`` (the projection). Returns the reply string verbatim.
    """
    action = parsed.get("action", "chat")

    if action == "add":
        text = parsed.get("text", "").strip()
        if not text:
            return "I didn't catch what to add. Could you say that again?"
        return commands.add(user_id, text, parsed.get("list", "inbox"), parsed.get("due_date"))

    if action == "complete":
        return commands.complete(user_id, parsed.get("task_id"), parsed.get("text_match"))

    if action == "delete":
        task_id = parsed.get("task_id")
        if task_id is None:
            return "Which task should I delete? Give me the task number."
        return commands.delete(user_id, task_id)

    if action == "move":
        task_id = parsed.get("task_id")
        if task_id is None:
            return "Which task should I move? Give me the task number."
        return commands.move(user_id, task_id, parsed.get("list", "next"), parsed.get("due_date"))

    if action == "mark_today":
        task_id = parsed.get("task_id")
        if task_id is None:
            return "Which task should I mark for today?"
        return commands.mark_today(user_id, task_id, parsed.get("is_today", True))

    if action == "clear_today":
        return commands.clear_today(user_id)

    if action == "list":
        list_name = parsed.get("list")
        tag = parsed.get("tag")
        if tag:
            return store.get_tasks_by_tag(user_id, tag)
        if list_name == "today":
            return store.get_today_tasks(user_id)
        if list_name == "overdue":
            return store.get_overdue_tasks(user_id)
        if list_name in store.VALID_LISTS:
            return store.get_tasks(user_id, list_name)
        return store.get_tasks(user_id)

    if action == "counts":
        return store.get_task_counts(user_id)

    if action == "completed":
        return store.get_completed_this_week(user_id)

    if action == "help":
        # Rendered from INTENTS — the same table the NLU prompt is built from
        # (invariant 4: help and capability cannot drift apart).
        examples = "\n".join(f"• {help_line}" for _, _, help_line in INTENTS)
        return f"I'm Jarvis, your GTD assistant. You can:\n{examples}"

    if action == "chat":
        return str(parsed.get("response", "I'm here to help with your tasks."))

    return "I'm not sure what to do with that. Try 'help' for options."


def poll_loop() -> None:
    store.init_db()
    user_id = _user_id()
    offset = 0
    log.info("Polling Telegram for messages")

    while True:
        try:
            for update in telegram.poll_updates(offset, POLL_TIMEOUT):
                offset = update["update_id"] + 1
                msg = update.get("message", {})
                from_id = msg.get("from", {}).get("id")
                chat_id = msg.get("chat", {}).get("id")
                text = (msg.get("text") or "").strip()

                if not text or from_id != user_id:
                    continue

                log.info("Message from %s: %s", from_id, text[:80])
                try:
                    telegram.send_chat_action(chat_id, "typing")
                    parsed = parse_with_ollama(text)
                    log.info("Parsed: %s", parsed.get("action", "unknown"))
                    telegram.send_message(chat_id, handle_action(parsed, user_id))
                except Exception:
                    log.exception("Error processing message")
                    telegram.send_message(chat_id, "Something went wrong. Try again?")

        except (HTTPError, URLError, TimeoutError) as e:
            log.warning("Poll error: %s — retrying in 5s", e)
            time.sleep(5)
        except Exception:
            log.exception("Unexpected error — retrying in 10s")
            time.sleep(10)


def main() -> None:
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(0))
    log.info("Jarvis GTD bot starting (model=%s)", OLLAMA_MODEL)
    poll_loop()


if __name__ == "__main__":
    main()
