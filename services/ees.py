import requests
import zipfile
from io import BytesIO
import fitz

service = "ees"

def gettoken(username, password):
	r = requests.get("https://app.easyeschool.it/v2/index.php/get/login/" + username + "/" + password + "/2/")
	return r.json()

def getbooks(token):
	r = requests.get("https://app.easyeschool.it/v2/index.php/get/books/" + token)
	return r.json()

def getchapters(token, bookid):
	r = requests.get("https://app.easyeschool.it/v2/index.php/get/chapters/" + token + "/" + bookid)
	return r.json()

def downloadchapter(token, bookid, chapterid, progress, total, done):
	r = requests.get("https://app.easyeschool.it/v2/index.php/get/chapter/" + token + "/" + bookid + "/" + chapterid, stream=True)
	length = int(r.headers.get("content-length", 1))
	file = b""
	for data in r.iter_content(chunk_size=102400):
		file += data
		progress(round(done + len(file) / length * total))
	return zipfile.ZipFile(BytesIO(file), "r")

def cover(token, bookid, data):
	r = requests.get("https://app.easyeschool.it/v2/index.php/get/cover/" + token + "/" + bookid)
	return r.content

def checktoken(token):
	return bool(getbooks(token))

def login(username, password):
	logindata = gettoken(username, password)
	token = logindata["token"]
	if not checktoken(token):
		print("Login failed: Invalid username and password combination")
	else:
		return token

def library(token):
	books = dict()
	for i in getbooks(token):
		books[str(i["bookid"])] = {"title": i["title"]}

	return books

def downloadbook(token, bookid, data, progress):
	pdf = fitz.Document()
	pcount = 1
	toc = []

	progress(0, "Getting book info")
	chapters = getchapters(token, bookid)
	chapterwidth = (98 - 5) / len(chapters)

	for i, chapter in enumerate(chapters):
		chapterstart = 5 + i * chapterwidth
		progress(chapterstart, f"Downloading unit {i + 1}/{len(chapters)}")
		chapterzip = downloadchapter(token, bookid, chapter["chapterid"], progress, chapterwidth, chapterstart)
		pdfpath = next(j for j in chapterzip.namelist() if "__MACOSX" not in j and j.endswith("pdf"))
		chapterpdf = fitz.Document(stream=chapterzip.read(pdfpath), filetype="pdf")
		pdf.insert_pdf(chapterpdf)
		toc.append([1, chapter["title"], pcount])
		pcount += len(chapterpdf)

	progress(98, "Applying toc")
	pdf.set_toc(toc)
	return pdf
