#!/usr/bin/env python3
"""Jarvis GTD bot — Telegram long-polling with Ollama parsing.

Run in-tree: ``python -m jarvis.bot``. Requires ``TELEGRAM_TOKEN`` and
``JARVIS_USER_ID`` in the environment (or gnome-keyring via ``secret-tool``).
"""

import json
import logging
import os
import signal
import subprocess
import sys
import time
from datetime import date
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from . import db

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("jarvis")


def _get_secret(name: str) -> str:
    val = os.environ.get(name)
    if val:
        return val
    return subprocess.check_output(
        ["secret-tool", "lookup", "service", "env", "key", name],
        text=True,
    ).strip()


TELEGRAM_TOKEN = _get_secret("TELEGRAM_TOKEN")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}"
OLLAMA_URL = os.environ.get("OLLAMA_URL", "http://localhost:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen3.5:9b")
POLL_TIMEOUT = 30
# Whose messages the bot accepts. A personal Telegram user id — sourced from the
# environment / keyring, never hard-coded (this repo is public).
USER_ID = int(_get_secret("JARVIS_USER_ID"))

SYSTEM_PROMPT = """You are Jarvis, a GTD (Getting Things Done) task manager assistant. Parse the user's message and return a JSON object with the action to take.

Today's date is {today}.

Available actions:
- {{"action": "add", "text": "task description", "list": "inbox|next|scheduled|someday", "due_date": "YYYY-MM-DD or null"}}
- {{"action": "complete", "task_id": number_or_null, "text_match": "partial text or null"}}
- {{"action": "delete", "task_id": number}}
- {{"action": "move", "task_id": number, "list": "inbox|next|scheduled|someday", "due_date": "YYYY-MM-DD or null"}}
- {{"action": "mark_today", "task_id": number, "is_today": true|false}}
- {{"action": "clear_today"}}
- {{"action": "list", "list": "inbox|next|scheduled|someday|all|today|overdue|null", "tag": "tag_name or null"}}
- {{"action": "counts"}}
- {{"action": "completed"}}
- {{"action": "help"}}
- {{"action": "chat", "response": "your conversational reply"}}

Rules:
- Default list for new tasks is "inbox" unless the user specifies otherwise.
- If the user says "done", "finished", "completed" followed by a task description, use "complete" with text_match.
- If the user says "done 3" or "complete #3", use "complete" with task_id.
- If the user says "delete 5" or "remove 5", use "delete" with task_id.
- If the user says "show inbox" or "list next", use "list" with the appropriate list name.
- If the user says "show all" or "tasks" or "show tasks", use "list" with list null.
- If the user says "today" or "what's for today", use "list" with list "today".
- If the user says "focus on 3" or "today 3", use "mark_today" with is_today true.
- If the user says "schedule X for next tuesday", convert to a date and use "add" with list "scheduled".
- If the user says "move 5 to next", use "move" with the task_id and list.
- For greetings, small talk, or questions not about tasks, use "chat" with a brief friendly response.
- Parse relative dates: "tomorrow" = next day, "next monday" = the coming Monday, etc.
- If ambiguous, prefer "add" to inbox — better to capture than to lose."""


def telegram_request(method: str, params: dict | None = None) -> dict | list | None:
    url = f"{TELEGRAM_API}/{method}"
    data = json.dumps(params or {}).encode()
    req = Request(url, data=data, headers={"Content-Type": "application/json"})
    with urlopen(req, timeout=POLL_TIMEOUT + 10) as resp:
        result = json.loads(resp.read())
    if not result.get("ok"):
        raise RuntimeError(f"Telegram API error: {result}")
    return result.get("result")


def send_reply(chat_id: int, text: str) -> None:
    telegram_request("sendMessage", {"chat_id": chat_id, "text": text})


def parse_with_ollama(message: str) -> dict:
    prompt = SYSTEM_PROMPT.format(today=date.today().isoformat())
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
    return json.loads(content)


def handle_action(parsed: dict) -> str:
    action = parsed.get("action", "chat")

    if action == "add":
        text = parsed.get("text", "").strip()
        if not text:
            return "I didn't catch what to add. Could you say that again?"
        list_name = parsed.get("list", "inbox")
        due_date = parsed.get("due_date")
        return db.add_task(USER_ID, text, list_name, due_date)

    if action == "complete":
        task_id = parsed.get("task_id")
        text_match = parsed.get("text_match")
        return db.complete_task(USER_ID, task_id, text_match)

    if action == "delete":
        task_id = parsed.get("task_id")
        if task_id is None:
            return "Which task should I delete? Give me the task number."
        return db.delete_task(USER_ID, task_id)

    if action == "move":
        task_id = parsed.get("task_id")
        new_list = parsed.get("list", "next")
        due_date = parsed.get("due_date")
        if task_id is None:
            return "Which task should I move? Give me the task number."
        return db.move_task(USER_ID, task_id, new_list, due_date)

    if action == "mark_today":
        task_id = parsed.get("task_id")
        is_today = parsed.get("is_today", True)
        if task_id is None:
            return "Which task should I mark for today?"
        return db.mark_today(USER_ID, task_id, is_today)

    if action == "clear_today":
        return db.clear_today(USER_ID)

    if action == "list":
        list_name = parsed.get("list")
        tag = parsed.get("tag")
        if tag:
            return db.get_tasks_by_tag(USER_ID, tag)
        if list_name == "today":
            return db.get_today_tasks(USER_ID)
        if list_name == "overdue":
            return db.get_overdue_tasks(USER_ID)
        if list_name in db.VALID_LISTS:
            return db.get_tasks(USER_ID, list_name)
        return db.get_tasks(USER_ID)

    if action == "counts":
        return db.get_task_counts(USER_ID)

    if action == "completed":
        return db.get_completed_this_week(USER_ID)

    if action == "help":
        return (
            "I'm Jarvis, your GTD assistant. You can:\n"
            "• Add tasks: \"buy milk\", \"call dentist @health\"\n"
            "• Complete: \"done buy milk\" or \"done 3\"\n"
            "• Lists: \"show inbox\", \"show all\", \"today\"\n"
            "• Schedule: \"schedule report for 2026-05-01\"\n"
            "• Move: \"move 5 to next\"\n"
            "• Focus: \"today 3\" to mark for today\n"
            "• Tags: \"show @work\"\n"
            "• Stats: \"counts\" or \"completed\""
        )

    if action == "chat":
        return parsed.get("response", "I'm here to help with your tasks.")

    return "I'm not sure what to do with that. Try 'help' for options."


def poll_loop() -> None:
    db.init_db()
    offset = 0
    log.info("Polling Telegram for messages")

    while True:
        try:
            updates = telegram_request("getUpdates", {
                "offset": offset,
                "timeout": POLL_TIMEOUT,
                "allowed_updates": ["message"],
            })
            for update in updates or []:
                offset = update["update_id"] + 1
                msg = update.get("message", {})
                user_id = msg.get("from", {}).get("id")
                chat_id = msg.get("chat", {}).get("id")
                text = (msg.get("text") or "").strip()

                if not text or user_id != USER_ID:
                    continue

                log.info("Message from %s: %s", user_id, text[:80])
                try:
                    telegram_request("sendChatAction", {"chat_id": chat_id, "action": "typing"})
                    parsed = parse_with_ollama(text)
                    log.info("Parsed: %s", parsed.get("action", "unknown"))
                    reply = handle_action(parsed)
                    send_reply(chat_id, reply)
                except Exception:
                    log.exception("Error processing message")
                    send_reply(chat_id, "Something went wrong. Try again?")

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
