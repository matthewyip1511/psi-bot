# AGENTS.md

Guidance for coding agents working in this repository.

## Project intent

This is a single-instance Telegram bot. At 08:05, 12:05, 16:05, and 20:05 every day in
`Asia/Singapore`, it fetches official NEA data through data.gov.sg and posts one channel update.
At the other hourly :05 slots through 23:05, it posts only if any region has PSI > 200 or PM2.5 > 150.
It does not fetch or broadcast on startup or restart. Every DM fetches the latest official
air-quality readings and replies privately, regardless of the time or alert thresholds.
If either feed fails validation or cannot be fetched, DMs receive `AIR_QUALITY_UNAVAILABLE`.
Group messages are ignored.

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
4. DMs may request current air-quality data only; never trigger a channel broadcast from a DM.
   Do not add other interactive commands or subscriptions without an explicit product requirement.
5. Never commit `.env`, tokens, API keys, channel IDs belonging to users, or captured private
   messages.
6. Send regular updates at 08:05, 12:05, 16:05, and 20:05 in `Asia/Singapore`. Check the other
   hourly :05 slots from 08:05 through 23:05 for PSI > 200 or PM2.5 > 150 in any region, sending
   at most one update per slot. Do not rely on the host timezone.
7. Do not fetch or broadcast on startup or restart; wait for a DM or the next scheduled slot.
8. Keep only one production replica unless distributed locking is added, or broadcasts will
   duplicate.

## Commands

```bash
pip install -e ".[dev]"
ruff check .
pytest
python -m psi_bot
```

Use `apply_patch` for hand-written changes. Before handing off, run the linter and full test suite.
