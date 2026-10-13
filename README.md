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
- **Final results** for the day's puzzle go out once a day at `RESULTS_TIME`.
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

You need the **Manage Server** permission on your Discord server.

1. **Create the bot.** Go to https://discord.com/developers/applications, click **New Application**, and name it.
2. **Get the token.** Open the **Bot** tab, click **Reset Token**, copy it, and paste it into `.env` after
   `DISCORD_TOKEN=`. The token is the bot's password. Never paste it in Discord or commit it. If it leaks, reset it.
3. **Turn on Message Content Intent.** It's on the same Bot tab, under *Privileged Gateway Intents*. Without it the
   bot can't read scores. Optional: turn off **Public Bot** so only you can add it. If Discord won't allow that,
   first set **Installation → Install Link** to *None*.
4. **Make the invite link.** Go to **OAuth2 → URL Generator**:
   - Scopes: `bot` and `applications.commands`
   - Bot permissions: View Channels, Send Messages, Read Message History, Add Reactions, Embed Links
5. **Invite it.** Open the generated URL, pick your server, and click **Authorize**.
6. **Start it.** Double-click `run_bot.bat`. The first run sets up `.venv` and installs the packages. Keep the
   window open while the bot runs.
7. **Point it at the channel.** In your Krillion channel, type `/krillion setchannel`.

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
