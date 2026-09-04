# AGENTS.md

Guidance for coding agents working in this repository.

## Project intent

This is a single-instance, broadcast-only Telegram bot. At the top of every hour in
`Asia/Singapore`, it fetches official NEA data through data.gov.sg and posts one channel update.
It never serves air-quality data in private chats; DMs receive only `PRIVATE_NOTICE`. Group
messages are ignored.

## Structure

- `src/psi_bot/data_gov.py`: HTTP access and response validation.
- `src/psi_bot/bands.py`: official threshold classification.
- `src/psi_bot/formatting.py`: Telegram-safe HTML message rendering.
- `src/psi_bot/bot.py`: Telegram handlers, scheduling, and lifecycle.
- `src/psi_bot/config.py`: environment parsing.
- `tests/`: unit tests; external services must be mocked.

## Required invariants

1. Keep the separate PSI and PM2.5 API timestamps visible. The feeds can update at different times.
2. Do not publish cached or fabricated readings when either endpoint fails.
3. Preserve the official band boundaries and add boundary tests for any band-related change.
4. Do not add interactive commands, subscriptions, or private-chat data without an explicit product
   requirement.
5. Never commit `.env`, tokens, API keys, channel IDs belonging to users, or captured private
   messages.
6. Schedule in `Asia/Singapore`; do not rely on the host machine's timezone.
7. Keep only one production replica unless distributed locking is added, or broadcasts will
   duplicate.

## Commands

```bash
pip install -e ".[dev]"
ruff check .
pytest
python -m psi_bot
```

Use `apply_patch` for hand-written changes. Before handing off, run the linter and full test suite.
