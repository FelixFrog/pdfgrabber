import requests
from hashlib import md5
from io import BytesIO
import fitz
import json
from base64 import b64decode

service = "myl"

def getlogindata(username, password):
	r = requests.post("https://www.cloudschooling.it/loescher/api/v1/api-token-auth/", json={"username": username, "password": md5(password.encode()).hexdigest()})
	return r.json()

def getlibrary(auth, isbn=""):
	r = requests.get("https://www.cloudschooling.it/mialim2/api/v1/book/sommari/" + isbn, headers={"Authorization": "JWT " + auth})
	return r.json()

def getdownloadurl(auth, url):
	r = requests.get("https://www.cloudschooling.it" + url, headers={"Authorization": "JWT " + auth})
	return r.json()

def downloadpdf(url, progress, total, done):
	r = requests.get(url, stream=True)
	length = int(r.headers.get("content-length", 1))
	file = b""
	for data in r.iter_content(chunk_size=102400):
		file += data
		progress(round(done + len(file) / length * total))
	return file

def cover(token, bookid, data):
	r = requests.get(data["cover"])
	return r.content

def getoutlines(item, notnumbered, level):
	subtoc = []
	subtoc.append([level, item["titolo"], item["pagina"] + notnumbered])
	for i in item["children"]:
		subtoc.extend(getoutlines(i, notnumbered, level + 1))
	return subtoc

def login(username, password):
	logindata = getlogindata(username, password)
	if "token" not in logindata:
		print("Login failed: " + logindata["detail"])
	else:
		return logindata["token"]

def checktoken(token):
	import time
	decodedjwt = json.loads(b64decode(token.split(".")[1] + "=="))
	expiry = int(decodedjwt["exp"])

	return int(time.time()) < expiry

def library(token):
	books = dict()
	for i in getlibrary(token):
		if i["tipologia"] == "d":
			continue
		books[str(i["opera"]["id"])] = {"title": i["opera"]["nome"], "pdfurl": i["opera"]["pdf"], "isbn": str(i["opera"]["isbn"]), "cover": i["opera"]["copertina"]}
	return books

def downloadbook(token, bookid, data, progress):
	progress(0, "Getting book info")
	downloadinfo = getdownloadurl(token, data["pdfurl"])

	progress(5, "Downloading pdf")
	pdf = fitz.Document(stream=downloadpdf(downloadinfo["url"], progress, 90, 5), filetype="pdf")
	toc = []

	progress(95, "Getting toc")
	spine = getlibrary(token, data["isbn"])

	notnumbered = spine["pagine_non_numerate"]
	labels = [page.get_label() for page in pdf]
	firstnum = next(index - int(num) + 1 for index, num in enumerate(labels) if num.isdigit())

	if notnumbered == 0 and firstnum != notnumbered and not labels[0].isdigit():
		# Not sure about this one, as of now this seems like a good guess. Maybe spine["raggruppamento"] means something?
		notnumbered += firstnum

	for i in spine["sezioni"]:
		toc.extend(getoutlines(i, notnumbered, 1))

	progress(98, "Applying toc")
	pdf.set_toc(toc)
	return pdf