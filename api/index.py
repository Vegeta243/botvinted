# Vercel entrypoint for the Bot Vinted dashboard
# Sets DB path to /tmp (writable on Vercel) before importing dashboard
import os
import config

# On Vercel, use /tmp for writable SQLite storage (ephemeral but functional)
if os.environ.get("VERCEL") or not os.path.exists(config.DB_PATH):
    config.DB_PATH = "/tmp/bot_vinted.db"

import database
database.init_db()

from dashboard import app  # noqa: F401 - Vercel ASGI entrypoint
