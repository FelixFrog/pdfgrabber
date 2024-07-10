import fitz
import requests
from base64 import b64decode
import json
from io import BytesIO
import tempfile
from zipfile import ZipFile
from playwright.sync_api import sync_playwright
from pathlib import Path
import re
import lib
import config

service = "snm"

key = "1cff42dabb60beaf1e3b57988af787246c63613ef60435a05c9c79b98a9b41c8"

configfile = config.getconfig()

def getlogindata(username, password):
	r = requests.post("https://npmoffline.sanoma.it/mcs/api/v1/login", json={"id": username, "password": password}, headers={"x-timezone-offset": "+0000"})
	return r.json()

def getlibrary(token):
	r = requests.get("https://npmoffline.sanoma.it/mcs/api/v1/books", headers={"x-auth-token": f"Bearer {token}"}, params={"app": "true"})
	return r.json()

def getuserproducts(token, username):
	r = requests.get(f"https://npmoffline.sanoma.it/mcs/users/{username}/products", headers={"x-auth-token": f"Bearer {token}"})
	return r.json()

def getbookinfo(token, username, bookid):
	r = requests.get(f"https://npmoffline.sanoma.it/mcs/users/{username}/products/books/{bookid}", params={"app": "true", "light": "true"}, headers={"x-auth-token": f"Bearer {token}"})
	return r.json()

def downloadzip(url, tmpfile, progress=False, total=0, done=0):
	showprogress = bool(progress)
	r = requests.get(url, stream=showprogress)
	length = int(r.headers.get("content-length", 1))
	for data in r.iter_content(chunk_size=102400):
		tmpfile.write(data)
		if showprogress:
			progress(round(done + tmpfile.tell() / length * total))

def getcover(url):
	r = requests.get(url)
	return r.content

def extractusername(token):
	contents = json.loads(b64decode(token.split(".")[1] + "==="))
	return contents["pes_authorization"]["id"]

def decrypt(data):
	# the original implementation used JS's String.charCodeAt(p) which returns a utf-16 codepoint value
	# we can't use urllib.parse.unquote because it doesn't support the "%uXXXX" esacaping (understandably, since it has never been part of any RFC)

	res = ""
	raw = BytesIO(b64decode(data))
	i = 0

	while (c := raw.read(1)):
		keyval = ord(key[(i - 1) % len(key)])
		if c != b"%":
			# if not escaped we use the ASCII value directly as the unicode codepoint
			res += chr(ord(c) - keyval)
		else:
			if ((c := raw.read(1)) == b"u"):
				# if escaped as "%uXXXX" we consider XXXX as the unicode codepoint value
				c = raw.read(4)
				res += chr(int(c, 16) - keyval)
			else:
				# if escaped as "%XX" we consider XX as a raw byte value
				c += raw.read(1)
				res += chr(int(c, 16) - keyval)
		i += 1
	return res

def parsestructure(mobj):
	# this is the most complex structure I have ever seen
	# each unit can be referred to by either its id or its "idUnit" string only if it is a top-level unit (WTF)
	# we have to create a tree to enumerate where each page is contained to be able to get the position of the bookmarks
	toc, labels = [], []

	unitnames = {i["id"]: i["title"] for i in mobj["units"]}
	groupcodetoid = {i["idUnit"]: i["id"] for i in mobj["units"]}
	pageidtolabel = {i["id"]: i["label"] for i in mobj["pages"]}
	first = []

	children = {}

	for i in mobj["units"]:
		if i["id"] not in children:
			children[i["id"]] = []
		if p := i.get("parent_unit"):
			children[p].append(i["id"])
		else:
			first.append(i["id"])

	for i in mobj["pages"]:
		if not i["chapter"]:
			parentid = groupcodetoid[i["idUnit"]]
		else:
			parentid = i["chapter"]["chapter_id"]
		children[parentid].append(i["id"])

	pageorder = {i["id"]: i["order"] for i in mobj["pages"]}
	def order(objid):
		if objid in pageidtolabel:
			return pageorder[objid]
		else:
			return min([order(i) for i in children[objid]] + [len(pageidtolabel) + 1])

	def generatetoc(ch, level):
		global tot
		ch.sort(key=order)
		for i in ch:
			if i in pageidtolabel:
				labels.append(pageidtolabel[i])
			else:
				toc.append([level, unitnames[i].strip(), len(labels) + 1])
				generatetoc(children[i], level + 1)

	first = [i for i in first if children[i]]
	generatetoc(first, 1)
	
	return toc, labels

def checkrequest(res):
	return not (res["result"] is None or res["code"] == 3)

def login(username, password):
	data = getlogindata(username, password)
	if not checkrequest(data):
		print("Login failed: " + data["message"])
	else:
		return data["result"]["data"]["access_token"] + "|" + data["result"]["data"]["refresh_token"]

def library(token):
	accesstoken, refreshtoken = token.split("|")
	books = {}
	library = getlibrary(accesstoken)
	if checkrequest(library):
		for book in library["result"]["data"]:
			books[str(book["gedi"])] = {"title": book["name"], "cover": book["image_url"], "isbn": book["isbn"]}
		return books

def cover(token, bookid, data):
	return getcover(data["cover"])

def checktoken(token):
	accesstoken, refreshtoken = token.split("|")
	username = extractusername(accesstoken)
	'''
	library = getlibrary(accesstoken)
	return checkrequest(library)
	'''
	products = getuserproducts(accesstoken, username)
	return checkrequest(products)

def downloadbook(token, bookid, data, progress):
	accesstoken, refreshtoken = token.split("|")
	username = extractusername(accesstoken)

	progress(1, "Getting book info")
	bookinfo = getbookinfo(accesstoken, username, bookid)
	if not checkrequest(bookinfo):
		print(f"Unable to get book info: {bookinfo['message']}")
		return
	url = bookinfo["result"]["data"]["url_download"]

	pdf = fitz.Document()

	with tempfile.TemporaryDirectory(prefix="sanoma.", ignore_cleanup_errors=True) as tmpdirfull:
		tmpdir = Path(tmpdirfull)
		zippath = tmpdir / f"{bookid}_light.zip"

		progress(3, "Downloading zip")
		downloadzip(url, open(zippath, "wb"), progress, 40, 3)
		
		progress(45, "Extracting zip")
		bookzip = ZipFile(zippath, "r")
		bookzip.extractall(path=tmpdir)

		master = open(tmpdir / "data" / "master.json")

		urlmatch = re.search(r"https:\\\/\\\/npmitaly-pro-gpd-files\.santillana\.es\\\/editorLM50\\\/([0-9]{6,8})\\\/pdf\\\/(.+?)\.pdf", master.read())
		master.seek(0)
		
		mobj = json.load(master)
		toc, labels = parsestructure(mobj)

		if urlmatch and configfile.getboolean(service, "SearchForOriginal", fallback=True):
			finalurl = urlmatch.group(0).replace(r"\/", r"/")
			pdfbytes = BytesIO()
			progress(47, "Downloading pdf")
			downloadzip(finalurl, pdfbytes, progress, 45, 47)
			pdf = fitz.Document(stream=pdfbytes, filetype="pdf")
		else:
			print("Error: can't find the source pdf of the book, resorting to manual rendering")
			print("Manual rendering not implemented yet, contact the developer!")
			exit()

	progress(98, "Applying toc/labels")
	if not pdf.get_toc() or not configfile.getboolean(service, "PreferOriginalToc", fallback=False):
		pdf.set_toc(toc)

	if not pdf.get_page_labels() or not configfile.getboolean(service, "PreferOriginalLabels", fallback=False):
		pdf.set_page_labels(lib.generatelabelsrule(labels))
	return pdf
