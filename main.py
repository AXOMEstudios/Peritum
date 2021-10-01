from flask import Flask, render_template, session, flash, redirect, request
from replit import db
from os import getenv

# setting up the app
app = Flask(__name__)
app.config["SECRET_KEY"] = getenv("SECRET")

# destroying getenv function to prevent later access
getenv = lambda: ""

# defining the views

@app.route("/")
def homepage():
  return render_template("index.html")

# starting the app capable for replit
app.run(host="0.0.0.0", port=8080)