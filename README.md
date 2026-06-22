# Channel To Summary

Discord bot that reads all messages at the end of every day and posts a recap per channel — powered by a local LLM via llama.cpp. No API keys, no cloud dependency.

## Features

- **Daily scheduled summaries** — runs automatically at a configurable time (default 23:59 UTC)
- **Per-channel opt-in** — enable/disable summaries per channel via slash commands
- **AI-generated summaries** — uses a local Qwen2.5-1.5B GGUF model via llama.cpp for proper abstractive summaries in French
- **Template fallback** — if no model is configured, produces structured template-based summaries (topic clusters, bug reports, announcements)
- **Discord mentions** — all participant names are rendered as clickable `@mentions`
- **Dedicated summary channel** — optionally route all recaps to a single channel with cross-post notifications in the original channel
- **Fully local** — zero external API calls, no data leaves your machine

## Prerequisites

- Docker & Docker Compose
- ~2 GB free RAM for the LLM model
- A Discord bot token ([how to create one](https://discord.com/developers/applications))

## Bot permissions

Invite the bot to your server using the OAuth2 URL generator in the Discord Developer Portal with the **bot** scope and the following permissions:

| Permission | Why it's needed |
|---|---|
| **View Channels** | See the channels where summaries are enabled |
| **Read Message History** | Fetch messages from the day to summarise |
| **Send Messages** | Post summaries and cross-post notifications |
| **Embed Links** | Post summaries as rich embeds |
| **Use Slash Commands** | Allow `/summary` commands |

**Invite URL format:**

```
https://discord.com/api/oauth2/authorize?client_id=YOUR_CLIENT_ID&permissions=2147568640&scope=bot
```

Replace `YOUR_CLIENT_ID` with your bot's application ID (found in the Discord Developer Portal under **OAuth2 > General**).

### Enable privileged intents

In the Discord Developer Portal, go to your application → **Bot** → **Privileged Gateway Intents** and enable **Message Content Intent**. This is required for the bot to read message content and generate summaries. The `PyNaCl` / `davey` warnings about voice support are harmless and can be ignored.

> The `/summary enable`, `/disable` and `/setchannel` commands additionally require the user to have the **Manage Channels** permission on the server. This is a user permission check, not a bot permission.

## Quick start

```bash
cp .env.example .env
# Edit .env and set DISCORD_TOKEN
docker compose up -d
```

The first build downloads the model (~1.1 GB). Subsequent starts are instant.

## Configuration

All settings go in `.env`:

| Variable | Default | Description |
|---|---|---|
| `DISCORD_TOKEN` | — | Your Discord bot token **(required)** |
| `SUMMARY_TIME` | `23:59` | Daily summary time (UTC, 24h) |
| `MESSAGE_FETCH_LIMIT` | `500` | Max messages to fetch per channel per day |
| `DATA_DIR` | `data` | Directory for persistent data (JSON DB) |
| `LLAMA_MODEL_PATH` | `models/qwen2.5-1.5b-instruct-q4_k_m.gguf` | Path to GGUF model. Set empty to disable LLM and use template-only mode |

### Without the LLM (lighter)

Set `LLAMA_MODEL_PATH=""` in `.env`. The bot will use the template-based summarizer only — no model download, ~120 MB container.

## Slash commands

All commands are under `/summary`:

| Command | Permission | Description |
|---|---|---|
| `/summary enable` | Manage Channels | Enable daily summaries for the current channel |
| `/summary disable` | Manage Channels | Disable summaries for the current channel |
| `/summary status` | anyone | Check if the current channel has summaries enabled |
| `/summary list` | anyone | Show all channels and their summary status |
| `/summary now` | anyone | Generate a summary right now for the current channel |
| `/summary setchannel #channel` | Manage Channels | Set a dedicated channel for recaps; a notification with a link is posted in the original channel |

## How the summarization works

### LLM mode (default)

1. Messages are time-clustered and formatted with `@mentions` and timestamps
2. The local Qwen2.5-1.5B model (4-bit quantized, ~1.1 GB) generates an abstractive summary in French
3. Inference runs entirely on CPU via `llama-cpp-python`, ~2 GB RAM

### Template mode (fallback)

When no LLM model is available:

1. Messages are grouped into 25-minute topic clusters
2. Each cluster is analysed for bugs, questions, links, reactions, and announcements
3. A reformulated sentence is generated using templates
4. Output is organised into structured sections with emoji prefixes (💬 📌)

## Project structure

```
Channel_To_Summary/
├── main.py              # Entry point
├── bot.py               # Discord client, slash commands, daily scheduler
├── summarizer.py        # LLM + template-based summarization
├── storage.py           # JSON-based persistent storage
├── config.py            # Environment variable loading
├── download_model.py    # GGUF model download script
├── Dockerfile           # Docker build
├── docker-compose.yml   # Docker Compose config
├── requirements.txt     # Python dependencies
├── .env.example         # Environment template
└── README.md            # This file
```

## Building from source

```bash
git clone <repo>
cd Channel_To_Summary
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 download_model.py
cp .env.example .env   # edit DISCORD_TOKEN
python3 main.py
```
