from flask import Flask, render_template, session, flash, redirect, request
from os import getenv
import axomeapis.auth as auth
import random
import pymongo

# setting up the app
app = Flask(__name__)
app.config["SECRET_KEY"] = getenv("SECRET")
app.config["PERMANENT_SESSION_LIFETIME"] = 2592000

client = pymongo.MongoClient("mongodb+srv://server:"+getenv("DB_SECRET")+"@axodb01.kpdbk.mongodb.net/peritum?retryWrites=true&w=majority")
db = client["peritum"]
users = db["users"]

# destroying getenv function to prevent later access
getenv = lambda: ""

# defining the views

@app.before_request
def before_req():
  session.permanent = True

@app.route("/")
def homepage():
  if "username" in session.keys():
    username = session["username"]
  else:
    username = ""
  return render_template("index.html", username=username)

@app.route("/signin")
def login():
  session["username"] = auth.login(request.args["usr"])

  if users.count_documents({"name": session["username"]}) < 1:
    users.insert_one({
      "name": session["username"],
      "articles": [],
      "pic": "/static/pic-default.png",
      "bio": "Hello, I'm "+session["username"]+"!"
    })
    return render_template("new.html", username=session["username"]) 
  
  return redirect("/")

@app.route("/logout")
def logout():
  try:
    del session["username"]
  except KeyError:
    pass
  return redirect("/")

@app.route("/profile/<username>")
def profile(username):
  if "username" in session.keys():
    user = session["username"]
  else:
    user = ""
  
  profile = users.find_one({"name": username})
  return render_template("profile.html", username=user, data=profile, name=profile["name"])

@app.route("/settings")
def settings():
  if "username" in session.keys():
    user = session["username"]
  else:
    redirect("/")
  
  profile = users.find_one({"name": user})
  return render_template("settings.html", username=user, data=profile, name=profile["name"])

@app.route("/settings/save-bio", methods=["POST"])
def settings_bio_save():
  if "username" in session.keys():
    user = session["username"]
  else:
    redirect("/")
  
  users.update({"name": user}, {"$set": {"bio": request.form["bio"]}})
  return redirect("/profile/"+user)

# defining error handlers

# starting the app capable for replit
app.run(host="0.0.0.0", port=8080)