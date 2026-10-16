
import os
from flask import Flask, render_template

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


if __name__ == "__main__":
    app.run()
