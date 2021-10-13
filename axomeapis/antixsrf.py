import random
import string

data = {}
chars = string.ascii_letters + string.digits

def generateToken():
  res = ""
  for i in range(16):
    res += random.choice(chars)
  return res

def createEndpoint(user, action):
  if not action in data.keys():
    data[action] = {}
  data[action][user] = generateToken()

  return data[action][user]

def validateEndpoint(token, user, action):
  if not action in data.keys():
    return False
  if token != data[action][user]:
    del data[action][user]
    return False
  del data[action][user]
  return True