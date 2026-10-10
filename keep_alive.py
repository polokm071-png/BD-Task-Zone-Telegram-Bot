"""Small Flask endpoint used to confirm that the bot process is alive."""

import threading

from flask import Flask

app = Flask(__name__)


@app.route("/")
def index() -> str:
    return "Bot is Alive"


def keep_alive() -> threading.Thread:
    """Run the health endpoint in a daemon thread on port 8080."""
    thread = threading.Thread(
        target=lambda: app.run(
            host="0.0.0.0",
            port=8080,
            use_reloader=False,
            threaded=True,
        ),
        name="flask-keep-alive",
        daemon=True,
    )
    thread.start()
    return thread
