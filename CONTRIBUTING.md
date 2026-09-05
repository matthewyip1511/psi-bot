# Contributing

Thank you for improving the Singapore PSI Telegram Bot.

## Set up a development environment

1. Use Python 3.11 or newer.
2. Create and activate a virtual environment.
3. Install the project and development tools:

   ```bash
   pip install -e ".[dev]"
   ```

4. Copy `.env.example` to `.env` only if you need a manual Telegram test. Automated tests do not
   require real credentials.

## Make a change

- Keep network access inside `DataGovSgClient`; use mocked HTTP transports in tests.
- Keep Telegram presentation logic in `formatting.py` and band rules in `bands.py`.
- Preserve all five regions and show the PSI and PM2.5 source timestamps separately.
- Keep scheduled broadcasts at 09:15, 14:15, and 20:15 in `Asia/Singapore`.
- Do not send extra broadcasts on startup or restart.
- Keep the bot broadcast-only. Private messages may receive only the fixed notice, and group
  messages must be ignored.
- Do not log or commit Telegram tokens or data.gov.sg API keys.

Add or update tests for behavior changes, especially threshold boundaries and malformed upstream
responses.

## Check your work

Run both checks before opening a pull request:

```bash
ruff check .
pytest
```

GitHub Actions runs these checks on Python 3.11 and 3.14 for pushes to `main` and pull requests
targeting `main`. Tests must use mocked external services and must not require real credentials.

## Pull requests

Describe the user-visible behavior, list the checks you ran, and call out changes to environment
variables or deployment steps. Keep unrelated refactors out of the same pull request.
