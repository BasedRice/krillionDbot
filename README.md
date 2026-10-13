# krillionDbot

A Discord bot that picks up Krillion scores pasted in chat and keeps a daily
leaderboard and the all-time record.

```
Krillion #90 🦐
225

🏮🫧🫧⬛🐟🐟🦑
```

## What it does

- **Picks up scores** in one watched channel per server and reacts ✅ to each one it saves.
- **First post counts.** A player's second post for the same puzzle gets 🔁 and is ignored. Edits don't change a score.
- **Checks the math.** Each tile is worth fixed points (🫧 10, 🐟 30, 🦑 60, 🏮 85, ⬛ 0). If the emoji row
  doesn't add up to the posted score, the post gets ⚠️. It still counts, but it isn't announced, and an admin can
  remove it. Rows with an unknown tile skip the check (the bot logs the tile so it can be added in
  `krillion/parsing.py`).
- **A "day" is a puzzle number**, so #90's board is everyone's #90 scores, whenever they posted.
- **Announces only big moments**: someone takes the lead on today's puzzle, matches the all-time record, or breaks it.
- **Final results** for the day's puzzle go out every night at midnight Eastern time.
- **Catches up.** On the first `/krillion setchannel` it imports the channel's whole history (no reactions).
  After every restart it reads anything posted while it was offline and reacts to those.

## Commands

| Command | Who | What |
|---|---|---|
| `/leaderboard [puzzle]` | everyone | Board for the newest puzzle, or any puzzle number |
| `/alltime` | everyone | All-time record and top 10 scores |
| `/stats [user]` | everyone | Games, average, best, daily wins, streaks |
| `/krillion setchannel [channel]` | Manage Server | Watch a channel and import its history |
| `/krillion remove <user> <puzzle>` | Manage Server | Delete a bad or fake score |
| `/krillion rescan` | Manage Server | Re-read the watched channel's history |

## Setup

You need a Windows PC with **Python 3.11 or newer** (https://www.python.org/downloads/). In the installer, tick
**Add python.exe to PATH**. To invite the bot, you or the server owner needs the **Manage Server** permission.

1. **Get the code.** Run `git clone https://github.com/BasedRice/krillionDbot.git`, or on GitHub use
   **Code → Download ZIP** and unzip it.
2. **Create the bot.** Go to https://discord.com/developers/applications, click **New Application**, and name it.
3. **Get the token and turn on Message Content Intent.** On the **Bot** tab, click **Reset Token** and copy the
   token. Lower on the same tab, under *Privileged Gateway Intents*, turn on **Message Content Intent** and save.
   Without it the bot can't read scores.
4. **Invite it.** Go to **OAuth2 → URL Generator**:
   - Scopes: `bot` and `applications.commands`
   - Bot permissions: View Channels, Send Messages, Read Message History, Add Reactions, Embed Links

   Open the generated URL, pick your server, and click **Authorize**. If you don't have Manage Server, send the URL
   to someone who does.
5. **First start.** Double-click `run_bot.bat`. It installs what it needs (about a minute), creates a `.env` file,
   and stops with "No bot token yet".
6. **Add the token.** Open `.env` in Notepad, paste the token after `DISCORD_TOKEN=`, and save. Leave the other
   settings alone: final results go out at midnight Eastern time wherever the PC is.
7. **Start it for real.** Double-click `run_bot.bat` again and wait for `Logged in as ...`. Keep the window open:
   closing it stops the bot.
8. **Point it at the channel.** In the Krillion channel, type `/krillion setchannel`. It imports the old scores and
   says how many it found.

The token is the bot's password. Never post it anywhere and never commit `.env`. If it leaks, click **Reset Token**
and paste the new one into `.env`.

On Mac or Linux, run these commands instead of `run_bot.bat`:
`python3 -m venv .venv && .venv/bin/pip install -r requirements.txt && cp .env.example .env`, edit `.env`, and then
run `.venv/bin/python bot.py`.

### Troubleshooting

- **"Discord rejected the token"**: reset the token on the Bot tab and paste the new one into `.env`.
- **"Turn on Message Content Intent"**: see step 3, then start the bot again.
- **Slash commands don't show up**: give it a minute, then press Ctrl+R in Discord to reload.
- **Bot shows offline**: the `run_bot.bat` window has to stay open and the PC has to stay on. When it starts again,
  it catches up on any scores posted while it was off.

## Settings (`.env`)

| Setting | Default | Meaning |
|---|---|---|
| `DISCORD_TOKEN` | none | Bot token (step 2) |
| `TIMEZONE` | `America/New_York` | Timezone for the daily results post |
| `RESULTS_TIME` | `00:00` | When final results go out (24-hour clock). A morning time still posts yesterday's puzzle |
| `VERIFY_SCORES` | `true` | Flag scores whose emoji row doesn't add up |
| `DB_PATH` | `%LOCALAPPDATA%\krillionDbot\krillion.db` | Score database. It's kept outside OneDrive on purpose |

## Tests

```bash
.venv/Scripts/python.exe -m unittest discover -s tests -t .
```
