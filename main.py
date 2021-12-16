from flask import Flask, render_template, session, flash, redirect, request, send_file, send_from_directory
import io
from difflib import SequenceMatcher
from os import getenv
import axomeapis.auth as auth
import axomeapis.antixsrf as antixsrf
import axomeapis.sitemap as sitemap
import pymongo
import datetime
from bson.objectid import ObjectId
import cloudinary
import random

# setting up the app
app = Flask(__name__)
app.config["SECRET_KEY"] = getenv("SECRET")
app.config["PERMANENT_SESSION_LIFETIME"] = 2592000

client = pymongo.MongoClient("mongodb+srv://peritum-backend:"+getenv("DB_SECRET")+"@axodb01.kpdbk.mongodb.net/peritum?retryWrites=true&w=majority")
db = client["peritum"]
users = db["users"]
articles = db["articles"]
likes = db["likes"]
errorlog = db["errors"]
comments = db["comments"]
messages = db["messages"]

cloudinary.config(
  cloud_name = "axome",
  api_key = getenv("CLOUDINARY_KEY"),
  api_secret = getenv("CLOUDINARY_SECRET")
)

articles.create_index([('article', pymongo.TEXT),('title', pymongo.TEXT)], name='text')

# destroying getenv function to prevent later access
getenv = lambda: ""

# defining the "algorithms" for recommendations

def rec_random():
  x = list(articles.aggregate([{"$sample": { "size": 5}}]))
  random.shuffle(x)
  return x

def limit(l, m):
  l = list(l)
  if len(l) <= m:
    return l
  else:
    return l[:m]

def rec_hottest():
  return limit(reversed(list(articles.find())), 5)

def recommend():
  return list(rec_hottest()) + list(rec_random())

def leaderboard():
  return list(users.find().sort([("reputation",pymongo.DESCENDING)]).limit(5))

howto_times = 0

howto = articles.find({
  "$text": {
    "$search": "How to make"
}}).limit(5)

def loadHowToSeries():
  return articles.find({
    "$text": {
    "$search": "How to make"
  }}).limit(5)
  
### defining the views ###

@app.before_request
def before_req():
  session.permanent = True

# home

@app.route("/")
def homepage():
  if "username" in session.keys():
    username = session["username"]
    if messages.count_documents({"user": username}, limit=1) > 0:
      for i in messages.find_one({"user": username})["messages"]:
        flash(i[0],i[1])
        messages.delete_one({"user": username})
  else:
    username = ""
  return render_template("index.html", username=username, hottest=rec_hottest(), random=rec_random(), lb=leaderboard(), howto=loadHowToSeries())

@app.route("/about")
def about_peritum():
  if "username" in session.keys():
    username = session["username"]
  else:
    username = ""
  return render_template("about.html", username=username)

# profile management

@app.route("/signin")
def login():
  session["username"] = auth.login(request.args["usr"])

  if users.count_documents({"name": session["username"]}) < 1:
    users.insert_one({
      "name": session["username"],
      "articles": [],
      "pic": "/static/pic-default.png",
      "bio": "Hello, I'm "+session["username"]+"!",
      "reputation": 0,
      "starred": []
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
  starred = articles.find({"_id": {"$in": profile["starred"]}})
  return render_template("profile.html", username=user, data=profile, name=profile["name"], articles=reversed(list(arts)), len_articles=len(list(profile["articles"])), rep=profile["reputation"], starred=list(starred))
@app.route("/settings")
def settings():
  if "username" in session.keys():
    user = session["username"]
  else:
    return redirect("/loginrequired")
  
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
      
  users.update({"name": user}, {"$set": {"pic": "https://res.cloudinary.com/axome/image/upload/"+request.form["pic"]}})

  flash("Image updated successfully.", "success")
  return redirect("/profile/"+user)

# write

@app.route("/write")
def writeArticle():
  if "username" in session.keys():
    user = session["username"]
  else:
    return render_template("loginrequired.html", username="")

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

  for i in "&%$/:=?":
    if i in request.form["title"]:
      flash("The title contains invalid characters (&%$/:= and ? are not allowed)","danger")
      return redirect("/write")
    if i in request.form["description"]:
      flash("The description contains invalid characters (&%$/:= and ? are not allowed)","danger")
      return redirect("/write")

  d = request.form
  i = articles.insert_one({
    "title": d["title"],
    "description": d["description"],
    "thumb": "https://res.cloudinary.com/axome/image/upload/w_240,h_180,c_scale/"+d["thumb"],
    "image": "https://res.cloudinary.com/axome/image/upload/"+d["thumb"],
    "article": d["article"],
    "author": user,
    "date": datetime.datetime.now().strftime("%d.%m.%Y, %H:%M"),
    "likes": 0
  })
  users.update_one({"name": user}, {"$push": {"articles": i.inserted_id}})
  comments.insert_one({
    "article": i.inserted_id,
    "comments": [],
    "title": d["title"],
    "activated": True
  })
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
  return render_template("read.html", d=d, username=username, article=d["article"].replace("\\","\\\\"),author=author, article_number=len(author["articles"]), rt=round(len(d["article"].split(" "))/150), recommend=rec_random(), token=(antixsrf.createEndpoint(username, "like") if username else ""))

@app.route("/loginrequired")
def intent():
  if "username" in session.keys():
    return redirect("/")
  return render_template("loginrequired.html", username="")

@app.route("/article/<i>/like")
def likeArticle(i):
  if "username" in session.keys():
    username = session["username"]
  else:
    return redirect("/loginrequired")

  if not antixsrf.validateEndpoint(request.args["token"], username, "like"):
    flash("An error occured. Please try that again.", "danger")
    return redirect("/article/"+i)

  author = articles.find_one({"_id": ObjectId(i)})["author"]

  if author == username:
    flash("Liking yourself is not possible.", "danger")
    return redirect("/article/"+i)

  if likes.count_documents({'name': username}, limit = 1) == 0:
    likes.insert_one({
      "name": username,
      "likes": []
    })
  
  if i in likes.find_one({"name": username})["likes"]:
    articles.update_one({"_id": ObjectId(i)}, {"$inc": {"likes": -1}})
    users.update_one({"name": author}, {"$inc": {"reputation": -2}})
    likes.update_one({"name": username}, {"$pull": {"likes": i}})
    flash("Article unliked.", "success")
  else:
    articles.update_one({"_id": ObjectId(i)}, {"$inc": {"likes": 1}})
    users.update_one({"name": author}, {"$inc": {"reputation": 2}})
    likes.update_one({"name": username}, {"$push": {"likes": i}})
    flash("Article liked!", "success")
  return redirect("/article/"+i)

# comment system

@app.route("/article/<i>/comments")
def readComments(i):
  rec = comments.find_one({"article": ObjectId(i)})
  return render_template("comments.html", comments=reversed(rec["comments"]), title=rec["title"], token=(antixsrf.createEndpoint(session["username"], "comment") if "username" in session.keys() else ""), article=i, username=(session["username"] if "username" in session.keys() else ""), activated=rec["activated"], author=articles.find_one({"_id": ObjectId(i)})["author"])

@app.route("/article/<i>/comments/post", methods=["POST"])
def postComment(i):
  if not "username" in session.keys():
    return redirect("/loginrequired")
  if not request.form["text"]:
    flash("Please provide a comment to send", "warning")
    return redirect("/article/"+i+"/comments")
  if len(request.form["text"]) >= 3000:
    flash("Your comment is too long (> 3000 characters)", "danger")
    return redirect("/article/"+i+"/comments")
  comms = comments.find_one({"article": ObjectId(i)})
  if not comms["activated"]:
    flash("Comments on this article are deactivated.", "danger")
    return redirect("/article/"+i+"/comments")
  if not antixsrf.validateEndpoint(request.form["token"], session["username"], "comment"):
    flash("Invalid security key, try again", "danger")
    return redirect("/article/"+i+"/comments")
  for comment in comms["comments"]:
    if (comment["author"] == session["username"]) and (SequenceMatcher(None, comment["text"], request.form["text"]).ratio() > 0.8):
      flash("You posted something too similar to this already.", "danger")
      return redirect("/article/"+i+"/comments")
    elif SequenceMatcher(None, comment["text"], request.form["text"]).ratio() > 0.92:
      flash(comment["author"]+" already said something very similar to this.", "danger")
      return redirect("/article/"+i+"/comments")
  comments.update_one({"article": ObjectId(i)}, {"$push": {"comments": {
    "author": session["username"],
    "text": request.form["text"],
    "date": datetime.datetime.now().strftime("%d.%m.%Y, %H:%M")
  }}})
  flash("Comment sent successfully.", "success")
  return redirect("/article/"+i+"/comments")

@app.route("/article/<i>/comments/toggle")
def toggleComments(i):
  if articles.find_one({"_id": ObjectId(i)})["author"] != session["username"]:
    flash("Not permitted", "danger")
    return redirect("/article/"+i+"/comments")
  if not antixsrf.validateEndpoint(request.args["token"], session["username"], "comment"):
    flash("Invalid security key, try again", "danger")
    return redirect("/article/"+i+"/comments")
  comments.update({"article": ObjectId(i)}, {"$set": {"activated": (not comments.find_one({"article": ObjectId(i)})["activated"]), "comments": []}})

  flash("Settings updated successfully.", "success")
  return redirect("/article/"+i+"/comments")

@app.route("/article/<i>/star")
def star_article(i):
  if not "username" in session.keys():
    return redirect("/loginrequired")

  if not antixsrf.validateEndpoint(request.args["token"], session["username"], "like"):
    flash("Invalid security key, try again.", "danger")
    return redirect("/article/"+i)

  if ObjectId(i) in users.find_one({"name": session["username"]})["starred"]:
    users.update_one({"name": session["username"]}, {"$pull": {"starred": ObjectId(i)}})
    flash("Unstarred article successfully, it has been removed from your profile page.", "success")
  else:
    users.update_one({"name": session["username"]}, {"$push": {"starred": ObjectId(i)}})
    flash("Starred article successfully, it's now visible on your profile page.", "success")
  return redirect("/article/"+i) 
# search

@app.route("/search")
def search():
  if "username" in session.keys():
    username = session["username"]
  else:
    username = ""
  
  results = articles.find({
    "$text": {
      "$search": "/^"+request.args["query"].replace("{", "").replace("}", "").replace("$", "")+"$/i"
    }})

  return render_template("search.html", results=list(results.limit(20).sort([("likes", 1)])), query=request.args["query"], username=username)

# defining errorhandlers

@app.errorhandler(404)
def error_404(e):
  return render_template("errors/404.html"), 404

def logError(req, err_code, err=""):
  errorlog.insert_one({
    "code": err_code,
    "url": req.url,
    "date": datetime.datetime.now().strftime("%d.%m.%Y, %H:%M"),
    "info": str(err)
  })

@app.errorhandler(400)
def error_400(e):
  logError(request, 400)
  return redirect("/errors/400")

@app.errorhandler(500)
def error_500(e):
  logError(request, 500, e)
  return redirect("/errors/500")

@app.route("/errors/<e>")
def errorMsg(e):
  return render_template("errors/"+e+".html"), int(e)

# generating the sitemap
  
@app.route("/sitemap.xml")
def sitemapView():
  sm = sitemap.generateSiteMap(list(articles.find()),
    list(users.find()), [
      "",
      "write",
      "settings",
      "about"
  ]).encode()
  return send_file(
    io.BytesIO(sm),
    mimetype='application/xml')

# stuff

@app.route("/apple-touch-icon.png")
def apple_touch_icon():
  return send_from_directory(app.static_folder, "touch-icon.png")
  
# starting the app capable for replit
app.run(host="0.0.0.0", port=8080)