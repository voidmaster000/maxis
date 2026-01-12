"""
FastAPI web server for bot status page
"""

import threading
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from discord.ext import commands

from bot.helper import resource_path

app = FastAPI()

templates = Jinja2Templates(directory=str(resource_path(".")))

# Serve static files (CSS, JS, images) from 'public' directory
app.mount("/public", StaticFiles(directory=str(resource_path("public"))), name="public")

globalBot: commands.Bot | None = None

INVITE_URL = "https://discord.com/api/oauth2/authorize?client_id=891518158790361138&permissions=8&scope=bot"


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    guild_count = len(globalBot.guilds) if globalBot else 0

    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "invite_url": INVITE_URL,
            "status": f"Online - {guild_count} servers",
        },
    )


def start_web_server(bot: commands.Bot, port: int = 8080):
    global globalBot
    globalBot = bot

    def run():
        import uvicorn

        uvicorn.run(
            app,
            host="0.0.0.0",
            port=port,
            log_level="info",
        )

    thread = threading.Thread(target=run, daemon=True)
    thread.start()

    print(f"Web server started on http://localhost:{port}")
