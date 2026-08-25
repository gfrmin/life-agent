"""Jarvis — the agent's GTD Telegram face: the loop, the NLU, the persona.

This is *reach*, not truth: it parses a human message into an intent (one small
model call), routes
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

from life_agent.core import ask_client, executor, secret
from life_agent.reach import telegram
from life_agent.tasks import commands, store

logging.basicConfig(
    level=os.environ.get("LOG_LEVEL", "INFO").upper(),
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger("jarvis")

# The NLU model (local Ollama deprecated 2026-08-17 — owner directive): one small
# cloud call per Telegram message, keyring-authed via core.llm. Env-overridable for
# an A/B, defaulting to the repo's dated haiku pin.
NLU_MODEL = os.environ.get("JARVIS_NLU_MODEL", "claude-haiku-4-5-20251001")
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
    ("question",
     '{"action": "question", "question": "the user\'s question, verbatim"}',
     'Ask: "what is my Israeli tax ID?" — answered from your documents with citations; '
     "reply g/b to grade it"),
    ("help",
     '{"action": "help"}',
     'Help: "help" or "?"'),
    ("chat",
     '{"action": "chat", "response": "your conversational reply"}',
     "Anything else: I'll just chat"),
)

# The last know-mode decision the owner can grade — one binding, most recent answer only
# (session state on the transport, not truth: the decision + verdict live behind the bridge;
# ask-live's /react covers deferred grading of anything older).
LAST_DECISION_ID: str | None = None

# The one-bit verdict vocabulary (reaction-loop economics: g/b, never prose).
_VERDICTS = {"g": "good", "good": "good", "👍": "good",
             "b": "bad", "bad": "bad", "👎": "bad"}


def verdict_valence(text: str) -> str | None:
    """Map a bare one-bit verdict message to its valence, or None if the message is
    anything else (then the normal NLU parses it). Deterministic — a verdict never
    round-trips through the model."""
    return _VERDICTS.get(text.strip().lower())

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
- If the user says "untoday 3" or "unmark 3", use "mark_today" with is_today false.
- If the user says "schedule X for next tuesday", convert to a date and use "add" with list "scheduled".
- If the user says "move 5 to next", use "move" with the task_id and list.
- If the user asks a question about their life, documents, dates, people, or facts — e.g. "what is my passport number?", "when does my lease end?" — use "question" with the question verbatim. Task commands always take precedence over "question".
- For greetings and small talk, use "chat" with a brief friendly response.
- Parse relative dates: "tomorrow" = next day, "next monday" = the coming Monday, etc.
- If ambiguous, prefer "add" to inbox — better to capture than to lose."""


def render_prompt(today: str) -> str:
    """The system prompt with the date substituted. .replace, not .format: the
    schema lines contain literal {} that .format would mangle."""
    return SYSTEM_PROMPT.replace("{today}", today)


def _user_id() -> int:
    """Whose messages the bot accepts — a personal id from env/keyring, never hard-coded."""
    return int(secret("JARVIS_USER_ID"))


def parse_intent(message: str) -> dict[str, Any]:
    """One NLU call: the message against the INTENTS prompt → the intent JSON.
    A non-JSON reply raises (the caller's error path names it — invariant 3,
    never a silently guessed intent). Code-fence wrappers are stripped: prompt
    steering asks for bare JSON, but a fenced reply is still an unambiguous one."""
    from life_agent.core.llm import anthropic_complete

    prompt = render_prompt(date.today().isoformat())
    reply = anthropic_complete(
        prompt + "\nReply with the JSON object only — no prose, no code fences.",
        message, model=NLU_MODEL, max_tokens=300, temperature=0.0)
    content = reply.text.strip()
    if content.startswith("```"):
        content = content.strip("`").removeprefix("json").strip()
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

    if action == "question":
        # The know mode, from the act surface (interaction contract: asking about your
        # life is *know*, whatever transport carried it): the executor read-path answers
        # with citations; the returned decision_id is what the next bare g/b binds to.
        global LAST_DECISION_ID
        q = str(parsed.get("question") or "").strip()
        if not q:
            return "What would you like to know?"
        r = ask_client.drive(q)
        if r.down:
            reply = ask_client.DOWN
        elif r.view is None:
            # the terminals-only regime answered (M5, §2.3): the leaf rendered the
            # text and recorded the decision — same grading contract as the full lane.
            reply = r.text or ask_client.DOWN
        else:
            reply = executor.render_view(r.view)
        decision_id = r.decision_id
        LAST_DECISION_ID = decision_id
        if decision_id:
            reply += "\n\nReply g (good) or b (bad) to grade this answer."
        return reply

    if action == "chat":
        return str(parsed.get("response", "I'm here to help with your tasks."))

    return "I'm not sure what to do with that. Try 'help' for options."


def poll_loop() -> None:
    global LAST_DECISION_ID
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
                    # A bare one-bit verdict binds to the last know-mode answer without a
                    # model round-trip (deterministic, reaction-loop economics). With no
                    # pending answer it falls through to the ordinary NLU.
                    valence = verdict_valence(text)
                    if valence and LAST_DECISION_ID:
                        reply = ask_client.react(LAST_DECISION_ID, valence)
                        LAST_DECISION_ID = None
                        telegram.send_message(chat_id, reply)
                        continue
                    telegram.send_chat_action(chat_id, "typing")
                    parsed = parse_intent(text)
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
    log.info("Jarvis GTD bot starting (model=%s)", NLU_MODEL)
    poll_loop()


if __name__ == "__main__":
    main()
