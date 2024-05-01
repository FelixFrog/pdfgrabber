import requests
import fitz
import lib
import config
from io import BytesIO
import zipfile
import tempfile
import sqlite3
import json

service = "hbs"

config = config.getconfig()

def getlogindata(username, password):
	r = requests.get("https://bce.mondadorieducation.it//app/mondadorieducation/login/loginJsonp", params={"username": username, "password": password})
	return r.json()

def getsessiontoken(jwt, internalusername, sessionid):
	data = {"username": internalusername, "sessionId": sessionid, "jwt": jwt}
	r = requests.post("https://ms-api.hubscuola.it/user/internalLogin", json=data)
	return r.json()

def getlibrary(token, platform):
	r = requests.get("https://ms-api.hubscuola.it/getLibrary/" +  platform, headers={"Token-Session": token})
	return r.json()

def downloadzip(token, bookid, progress, total, done, chapterid="publication"):
	suburl = "downloadPackage" if chapterid == "publication" else "public"
	r = requests.get("https://ms-mms.hubscuola.it/" + "/".join([suburl, bookid, chapterid + ".zip"]), params={"tokenId": token, "app": "v2"}, headers={"Token-Session": token}, stream=True)
	length = int(r.headers.get("content-length", 1))
	file = b""
	for data in r.iter_content(chunk_size=102400):
		file += data
		progress(round(done + len(file) / length * total))
	return zipfile.ZipFile(BytesIO(file), "r")

def cover(token, bookid, data):
	r = requests.get(data["cover"], params={"tokenId": token}, headers={"Token-Session": token}, auth=("testusername", "testpassword"))
	return r.content

def checktoken(token):
	r = requests.get("https://ms-api.hubscuola.it/annotation/user-preferences", headers={"Token-Session": token})
	return not "not valid" in r.text

def extractpage(zipfile, chapterid, pageid):
	file = zipfile.read(str(chapterid) + "/" + str(pageid) + ".pdf")
	return fitz.Document(stream=file, filetype="pdf")

def login(username, password):
	logindata = getlogindata(username, password)
	if not logindata["data"]:
		print("Login failed: " + logindata["error"])
	else:
		session = getsessiontoken(logindata["data"]["hubEncryptedUser"], logindata["data"]["username"], logindata["data"]["sessionId"])
		return session["tokenId"]

def library(token):
	books = dict()
	def getbooktitle(book):
		title = i["title"]
		if volume := i.get("volume"):
			title += f" {volume}"
		if subtitle := i.get("subtitle"):
			title += f" - {subtitle}"
		return title

	for platform in ["young", "kids"]:
		for i in getlibrary(token, platform):
			books[str(i["id"])] = {"title": getbooktitle(i), "cover": i["coverBig"], "platform": platform}

	return books

def downloadbook(token, bookid, data, progress):
	progress(0, "Getting book info")
	bookinfozip = downloadzip(token, bookid, progress, 5, 0)
	with tempfile.NamedTemporaryFile() as tf:
		tf.write(bookinfozip.read("publication/publication.db"))
		cur = sqlite3.connect(tf.name).cursor()
		bookinfo = json.loads(cur.execute("SELECT offline_value FROM 'offline_tbl' WHERE offline_path = 'meyoung/publication/" + bookid + "';").fetchone()[0])

	pdf = fitz.Document()
	toc = []

	pagecount = 1
	chapters = bookinfo["indexContents"]["chapters"]
	chapterwidth = (98 - 5) / len(chapters)

	for i, chapter in enumerate(chapters):
		chapterstart = 5 + (i * chapterwidth)
		progress(chapterstart, f"Downloading unit {i + 1}/{len(chapters)}")
		chapterzip = downloadzip(token, bookid, progress, chapterwidth, chapterstart, str(chapter["chapterId"]))
		toc.append([1, chapter["title"], pagecount])
		for j in chapter["children"]:
			if isinstance(j, int):
				if j in bookinfo["pagesId"]:
					pagepdf = extractpage(chapterzip, chapter["chapterId"], j)
					pdf.insert_pdf(pagepdf)
					pagecount += 1
			else:
				if len(chapter["children"]) > 1:
					toc.append([2, j["title"], pagecount])
				for k in j["children"]:
					if k in bookinfo["pagesId"]:
						pagepdf = extractpage(chapterzip, chapter["chapterId"], k)
						pdf.insert_pdf(pagepdf)
						pagecount += 1

	progress(98, "Applying toc/labels")
	if config.getboolean(service, "PageLabels", fallback=False):
		labels = bookinfo["multiRangeIndex"]["valToLabel"].values()
		pdf.set_page_labels(lib.generatelabelsrule(labels))
	pdf.set_toc(toc)
	return pdf