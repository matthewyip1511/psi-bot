# Singapore PSI Telegram Bot

A small Python service that posts Singapore's latest **24-hour PSI** and **1-hour PM2.5**
readings to a Telegram channel at five minutes past every hour (Singapore time). It reports all five
regions, each reading's official NEA band, the national range, and separate source timestamps. An
optional quiet period can suppress the 2:00 AM through 7:00 AM scheduled updates.

The bot is intentionally broadcast-only. Telegram does not provide a switch that prevents a user
from opening a bot DM, so every private message receives only this response:

> This bot is for blasting messages only.

Messages in groups and channel posts are ignored.

## Data sources and bands

The service reads the latest values from the official data.gov.sg real-time endpoints:

- [24-hour PSI API](https://api-open.data.gov.sg/v2/real-time/api/psi)
- [1-hour PM2.5 API](https://api-open.data.gov.sg/v2/real-time/api/pm25)
- [Dataset page supplied for this project][psi-dataset]

Bands follow [NEA's published air-quality table](https://www.haze.gov.sg/):

| 24-hour PSI | Descriptor | 1-hour PM2.5 (µg/m³) | Band |
|---:|---|---:|---|
| 0–50 | Good | 0–55 | 1 — Normal |
| 51–100 | Moderate | 56–150 | 2 — Elevated |
| 101–200 | Unhealthy | 151–250 | 3 — High |
| 201–300 | Very Unhealthy | ≥251 | 4 — Very High |
| >300 | Hazardous | — | — |

## Telegram setup

1. Open a chat with [@BotFather](https://t.me/BotFather), run `/newbot`, and keep the token secret.
2. Add the bot to the target channel as an administrator.
3. Grant it the **Post Messages** permission. It does not need permission to edit or delete posts.
4. Choose the channel identifier:
   - Public channel: use its username, for example `@my_air_quality_channel`.
   - Private channel: use its numeric ID, normally beginning with `-100`. Follow the safe lookup
     steps below.

### Find a private channel's numeric ID

The project includes a helper that asks Telegram directly through your own bot, so you do not have
to send channel details to a third-party ID bot:

1. Install the project and copy `.env.example` to `.env` as described below.
2. Put the BotFather token in `TELEGRAM_BOT_TOKEN`. The channel ID can remain as its placeholder
   while running this helper.
3. Add the bot to the destination channel as an administrator with **Post Messages** permission.
4. Ensure `psi-bot` is stopped; Telegram permits only one long-polling process per bot token.
5. Run the helper. On macOS/Linux use `.venv/bin/python -m psi_bot.channel_id`; on Windows use
   `.venv\Scripts\python -m psi_bot.channel_id`. While it is waiting, publish a temporary post in
   the destination channel from the Telegram phone or desktop app.
6. Copy the printed `-100...` number into `TELEGRAM_CHANNEL_ID` in `.env`. You may delete the
   temporary channel post afterward.

If the helper finds nothing, confirm the bot was already an administrator when the new post was
created, then run it again. For a public channel, using `@channel_username` is simpler and the
lookup is unnecessary.

## Run locally

Python 3.11 or newer is required.

### Quick install (macOS/Linux)

The included scripts create an isolated environment and start the service:

```bash
sh install.sh
```

Edit the newly created `.env`, then run:

```bash
sh start.sh
```

`install.sh` will not overwrite an existing `.env`. Run the service under a supervisor such as
systemd if it needs to stay online continuously; only run one copy, or the channel will receive
duplicate hourly posts.

### Manual install (all platforms)

```bash
python -m venv .venv
```

Activate the environment on Windows PowerShell:

```powershell
.venv\Scripts\Activate.ps1
```

Or on macOS/Linux:

```bash
source .venv/bin/activate
```

Install and configure the project:

```bash
pip install -e .
cp .env.example .env
```

On Windows, use `Copy-Item .env.example .env` instead of `cp`. Edit `.env`, then start the bot:

```bash
psi-bot
```

You can also run it as a module:

```bash
python -m psi_bot
```

The first scheduled post is at the next `HH:05` mark in Singapore. Set
`SEND_ON_STARTUP=true` while commissioning the bot if you also want an immediate post. Leave it
`false` in normal operation to avoid an extra post after restarts.

Set `DISABLE_NIGHT_UPDATES=true` to suppress broadcasts scheduled from 2:05 AM through 7:05 AM
Singapore time. The final overnight post is then at 1:05 AM, and hourly posting resumes at 8:05 AM.
This quiet period also suppresses `SEND_ON_STARTUP` from 2:00–7:59 AM if the service restarts during
those hours.

## Configuration

| Variable | Required | Meaning |
|---|---|---|
| `TELEGRAM_BOT_TOKEN` | Yes | Token issued by BotFather. |
| `TELEGRAM_CHANNEL_ID` | Yes | `@public_username` or numeric channel ID such as `-100…`. |
| `DATA_GOV_SG_API_KEY` | No | Adds higher data.gov.sg rate limits; sent in the `x-api-key` header. |
| `SEND_ON_STARTUP` | No | `true` sends once on startup; default is `false`. |
| `DISABLE_NIGHT_UPDATES` | No | `true` suppresses updates from 2:00–7:59 AM SGT; default is `false`. |
| `LOG_LEVEL` | No | Python log level; default is `INFO`. |

Never commit `.env`; it is ignored by Git.

The `.env` format intentionally has no spaces around `=`. Paste each value after its own equals
sign, for example `TELEGRAM_CHANNEL_ID=-1001234567890`. Leave `DATA_GOV_SG_API_KEY=` empty if you
do not have a source API key; the public feeds still work without one.

## Example post

Telegram renders the regional values, ranges, and band classifications in bold. The underlying
message is otherwise kept simple and readable:

```text
🇸🇬 Singapore Air Quality Update
Sent: Friday, 4 September 2026 at 11:05 PM SGT

24-hour PSI
Data time: Friday, 4 September 2026 at 11:00 PM SGT
Singapore range: 87–123 (Moderate to Unhealthy)
• North: 88 — Moderate
...

1-hour PM2.5
Data time: Friday, 4 September 2026 at 10:00 PM SGT
Singapore range: 54–83 µg/m³ (Normal to Elevated)
• North: 56 µg/m³ — Band 2 — Elevated
...

Source: NEA via data.gov.sg
```

The API is retried up to three times for transient failures. If data.gov.sg or Telegram remains
unavailable, that hour is logged and skipped instead of publishing stale or misleading data.

## Development

```bash
pip install -e ".[dev]"
pytest
ruff check .
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for contribution guidance.

[psi-dataset]: https://data.gov.sg/datasets/d_fe37906a0182569d891506e815e819b7/view
