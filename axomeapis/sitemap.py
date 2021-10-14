def generateSiteMap(articles, users, extra=[]):
  global res
  res = ""
  def addUrl(url):
    global res
    res += "<url><loc>"+str(url)+"</loc></url>"

  start = '''<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  {{data}}
</urlset>'''

  for i in articles:
    addUrl("https://peritum.axome.de/article/"+str(i["_id"]))

  for i in users:
    addUrl("https://peritum.axome.de/profile/"+str(i["name"]))

  for i in extra:
    addUrl("https://peritum.axome.de/"+str(i))

  return start.replace("{{data}}", res)