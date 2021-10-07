from requests import post

cache = {}

# Before pushing to production: enter the URL you specified in the URL of the Signin-Button or link here!

# https://auth.axome.de/signin?url=SOMETHING
# Needed part of this url:         ^^^^^^^^^

URL = "https:%2F%2Fperitum.axome.repl.co%2Fsignin"

if not URL:
  raise Exception("It looks like you forgot to specify the URL used at the button or link for signin in the client file. Visit auth.py and enter the proper URL.")

def login(token):
  if token in cache.keys(): return cache[token]
  x = post("https://auth.axome.repl.co/check",{"usr": token}).text.split(";")
  if x[1] != URL:
    raise Exception("The token of the user comes from another platform. To prevent malicious access to the users account on this platform, probably performed by the other platform, the login has been terminated. This error might happen when you did not correctly configure the URL constant at the top of the client file. To fix this issue, enter this URL in the constant: "+x[1])
    return ""
  if len(x[0]) > 20:
    raise Exception("The AXOME server rejected the given token or did not find it.")
  cache[token] = x[0]
  return x[0]

def logout(token):
  x = cache[token]
  del cache[token]
  return x
  
def getUser(token):
  if token in cache.keys(): return cache[token]
  x = post("https://auth.axome.repl.co/check",{"usr": token}).text.split(";")[0]
  if len(x) > 20:
    raise Exception("The AXOME server rejected the given token or did not find it.")
  cache[token] = x
  return x