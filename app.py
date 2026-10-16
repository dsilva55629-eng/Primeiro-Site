
import os
from flask import Flask, render_template, send_from_directory

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    "chave-temporaria-para-desenvolvimento"
)


@app.route("/")
def inicio():
    return render_template("index.html")


@app.route("/saude")
def saude():
    return {"status": "online"}


@app.route("/service-worker.js")
def service_worker():
    response = send_from_directory(
        app.root_path,
        "service-worker.js",
        mimetype="application/javascript"
    )
    response.headers["Service-Worker-Allowed"] = "/"
    response.headers["Cache-Control"] = "no-cache"
    return response


if __name__ == "__main__":
    app.run()
