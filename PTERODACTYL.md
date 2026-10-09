# Production deployment on Pterodactyl

## Runtime

- Python: **3.14.x** (the repository CI currently validates Python 3.14).
- Install command: `python -m pip install -r requirements.txt`
- Startup command: `python start.py`
- Alternative entry point: `python main.py`

## Required environment

Configure these values in the Pterodactyl startup/environment panel. Do not commit real credentials.

| Variable | Required | Meaning |
|---|---|---|
| `VK_TOKEN` | Yes | Community access token; keep private |
| `VK_GROUP_ID` | Yes | Positive numeric VK community ID, without a minus sign |
| `VK_API_VERSION` | No | VK API version; default `5.199` |
| `ADMIN_IDS` | No | Comma-separated positive VK user IDs allowed to manage roles |
| `XP_PER_MESSAGE` | No | XP reward configuration |
| `XP_PER_LEVEL` | No | Legacy setting; the current nonlinear level thresholds are defined by `XPSystem` and do not use this variable |
| `MAX_RP_TEXT` | No | Maximum RP text length |
| `LOG_LEVEL` | No | Logging level; default `INFO` |
| `FORBIDDEN_WORDS` | No | Additional AutoMod words, comma-separated |

`VK_TOKEN` and `VK_GROUP_ID` are validated at startup. If either is missing or malformed, the process exits with a configuration error.

## Persistent data

- Main database: `data/bot.db`
- Marriage database: `data/marriage.db`
- Keep the `data/` directory on persistent storage when recreating or updating the server.
- Back up the main database before schema or deployment changes. Example:

  `python -m scripts.backup_database --database data/bot.db --destination data/backups/vk-moderator.sqlite3`

- Restore from a backup only during maintenance. The restore API creates a safety copy of the current database before replacing it. Example: `python -m scripts.restore_database --database data/bot.db --source data/backups/vk-moderator.sqlite3`.

## First-run checklist

1. Set the Python egg/runtime to 3.14.x.
2. Install `requirements.txt`.
3. Set `VK_TOKEN`, `VK_GROUP_ID`, and at least one trusted ID in `ADMIN_IDS`.
4. Confirm the community token has the permissions needed for message handling and moderation methods.
5. Start `python start.py` and inspect the startup logs.
6. Verify the bot receives a test message and can send a reply.
7. Enable Pterodactyl's automatic restart policy for unexpected process exits; the app logs fatal errors and exits rather than silently continuing in a broken state.
8. Verify moderation actions only in a test conversation/community where you have authorization.
9. Confirm a backup can be created and restored before relying on production data.

The repository CI and static security workflow do **not** verify a real VK token, community permissions, or a live Pterodactyl restart. Those remain deployment checks.
