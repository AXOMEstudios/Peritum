from flask import Flask, render_template, session, flash, redirect, request
from os import getenv
import axomeapis.auth as auth
import axomeapis.antixsrf as antixsrf
import pymongo
import datetime
from bson.objectid import ObjectId
import cloudinary
import random

# setting up the app
app = Flask(__name__)
app.config["SECRET_KEY"] = getenv("SECRET")
app.config["PERMANENT_SESSION_LIFETIME"] = 2592000

client = pymongo.MongoClient("mongodb+srv://server:"+getenv("DB_SECRET")+"@axodb01.kpdbk.mongodb.net/peritum?retryWrites=true&w=majority")
db = client["peritum"]
users = db["users"]
articles = db["articles"]

cloudinary.config(
  cloud_name = "axome",
  api_key = getenv("CLOUDINARY_KEY"),
  api_secret = getenv("CLOUDINARY_SECRET")
)

# destroying getenv function to prevent later access
getenv = lambda: ""

# defining the "algorithm" for recommendations

def rec_random():
  x = list(articles.aggregate([{"$sample": { "size": 5}}]))
  random.shuffle(x)
  return x

def rec_hottest():
  return articles.find().limit(5)

def recommend():
  return list(rec_hottest()) + list(rec_random())

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
  return render_template("index.html", username=username, hottest=rec_hottest(), random=rec_random())

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
  arts = articles.find({"author": username})
  return render_template("profile.html", username=user, data=profile, name=profile["name"], articles=arts)

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
  flash("Biography updated successfully.", "success")
  return redirect("/profile/"+user)

@app.route("/settings/save-pic", methods=["POST"])
def settings_pic_save():
  if "username" in session.keys():
    user = session["username"]
  else:
    redirect("/")

  for i in ["png", "jpg", "jpeg", "webp", "tiff", "ico"]:
    if request.form["pic"].endswith("."+i):
      break
  else:
    flash("The image format is not supported. Supportet formats: png, jpg, jpeg, webp, tiff, ico.", "danger")
    return redirect("/settings")
      
  users.update({"name": user}, {"$set": {"pic": request.form["pic"]}})

  flash("Image updated successfully.", "success")
  return redirect("/profile/"+user)

@app.route("/write")
def writeArticle():
  if "username" in session.keys():
    user = session["username"]
  else:
    redirect("/")

  t = antixsrf.createEndpoint(user, "post")
    
  return render_template("write.html", username=user, token=t)

@app.route("/write/post", methods=["POST"])
def postArticle():
  if "username" in session.keys():
    user = session["username"]
  else:
    redirect("/")

  if not antixsrf.validateEndpoint(request.form["token"], user, "post"):
    flash("Invalid verification token. Try again.", "danger")
    return redirect("/write")
  
  for i in ["title", "description", "thumb", "article"]:
    if not request.form[i]:
      flash("You did not provide a(n) "+i, "warning")
      return redirect("/write")

  temp = ""
  for i in request.form.values():
    temp += i
  if len(temp) > (1000*1024):
    flash("Your article is too big to upload (over 1MB)", "warning")
    return redirect("/write")

  for i in ["png", "jpg", "jpeg", "webp", "tiff", "ico"]:
    if request.form["thumb"].endswith("."+i):
      break
  else:
    flash("The image format is not supported. Supportet formats: png, jpg, jpeg, webp, tiff, ico.", "danger")
    return redirect("/write")

  d = request.form
  i = articles.insert_one({
    "title": d["title"],
    "description": d["description"],
    "thumb": "https://res.cloudinary.com/axome/image/upload/w_240,h_180,c_scale/"+d["thumb"],
    "image": "https://res.cloudinary.com/axome/image/upload/"+d["thumb"],
    "article": d["article"],
    "author": user,
    "date": datetime.datetime.now().strftime("%d.%m.%Y, %H:%M")
  })
  users.update_one({"name": user}, {"$push": {"articles": i.inserted_id}})
  flash("Article published successfully.", "success")

  return redirect("/article/"+str(i.inserted_id))

@app.route("/article/<i>")
def readArticle(i):
  if "username" in session.keys():
    username = session["username"]
  else:
    username = ""
  d = articles.find_one({"_id": ObjectId(i)})
  author = users.find_one({"name": d["author"]})
  return render_template("read.html", d=d, username=username, article=d["article"].replace("\\","\\\\"),author=author, article_number=len(author["articles"]), rt=round(len(d["article"].split(" "))/150), recommend=recommend())

# starting the app capable for replit
app.run(host="0.0.0.0", port=8080)