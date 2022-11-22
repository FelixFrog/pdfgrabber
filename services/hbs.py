import requests
import fitz
import lib
import config

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

def getbookinfo(token, bookid, platform):
	r = requests.get("https://ms-api.hubscuola.it/me" + platform + "/publication/" + str(bookid), headers={"Token-Session": token})
	return r.json()

def downloadchapter(token, bookid, chapterid, progress, total, done):
	from io import BytesIO
	import zipfile
	
	r = requests.get("https://ms-mms.hubscuola.it/public/" + str(bookid) + "/" + str(chapterid) + ".zip", params={"tokenId": token, "app": "v2"}, headers={"Token-Session": token}, auth=("testusername", "testpassword"), stream=True)
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

def getauth(jwt, bookid, platform):
	r = requests.post("https://ms-pdf.hubscuola.it/i/d/" + bookid + "/auth", json={"jwt": jwt, "origin": "https://" + platform + ".hubscuola.it/viewer/" + bookid + "?page=1"}, headers={"PSPDFKit-Platform": "web", "PSPDFKit-Version": "protocol=3, client=2020.6.0, client-git=63c8a36705"})
	return r.json()

def downloadpdf(token, bookid, layerhandle, progress, total, done):
	r = requests.get("https://ms-pdf.hubscuola.it/i/d/" + bookid + "/h/" + layerhandle + "/pdf?token=" + token, stream=True)
	length = int(r.headers.get("content-length", 1))
	file = b""
	for data in r.iter_content(chunk_size=102400):
		file += data
		progress(round(done + len(file) / length * total))
	return file

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

def downloadbook_legacy(token, bookid, data, progress):
	progress(0, "Getting book info")
	bookinfo = getbookinfo(token, bookid)

	pdf = fitz.Document()
	toc = []

	pagecount = 1
	chapters = bookinfo["indexContents"]["chapters"]
	chapterwidth = (98 - 5) / len(chapters)

	for i, chapter in enumerate(chapters):
		chapterstart = 5 + (i * chapterwidth)
		progress(chapterstart, f"Downloading unit {i + 1}/{len(chapters)}")
		chapterzip = downloadchapter(token, bookid, chapter["chapterId"], progress, chapterwidth, chapterstart)
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

def downloadbook_new(token, bookid, data, progress):
	progress(0, "Getting book info")
	bookinfo = getbookinfo(token, bookid, data["platform"])

	progress(2, "Fetching authentication data")
	auth = getauth(bookinfo["jwt"], bookid, data["platform"])

	progress(4, "Downloading unencrypted pdf")
	pdfbytes = downloadpdf(auth["token"], bookid, auth["layerHandle"], progress, 91, 4)

	pdf = fitz.Document(stream=pdfbytes, filetype="pdf")

	progress(98, "Applying toc/labels")
	toc = []

	pagecount = 1
	chapters = bookinfo["indexContents"]["chapters"]

	for i, chapter in enumerate(chapters):
		toc.append([1, chapter["title"], pagecount])
		for j in chapter["children"]:
			if isinstance(j, int):
				if j in bookinfo["pagesId"]:
					pagecount += 1
			else:
				if len(chapter["children"]) > 1:
					toc.append([2, j["title"], pagecount])
				for k in j["children"]:
					if k in bookinfo["pagesId"]:
						pagecount += 1

	if config.getboolean(service, "PageLabels", fallback=False):
		labels = bookinfo["multiRangeIndex"]["valToLabel"].values()
		pdf.set_page_labels(lib.generatelabelsrule(labels))
	pdf.set_toc(toc)
	return pdf

def downloadbook(token, bookid, data, progress):
	if config.getboolean(service, "UseLegecy", fallback=False):
		pdf = downloadbook_legacy(token, bookid, data, progress)
	else:
		pdf = downloadbook_new(token, bookid, data, progress)
	return pdf