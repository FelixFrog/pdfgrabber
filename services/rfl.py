import json
import requests
from Crypto.Cipher import AES
from base64 import b64encode, b64decode
import xml.etree.ElementTree as et
import config
import fitz
import lib

service = "rfl"

pwdkey = "cre!reDefat&2Nex"
pwdiv = "gETr?sTas*Ku8ewa"

config = config.getconfig()

def getlogindata(username, encrpassword):
	r = requests.get("https://www.raffaellodigitale.it/media/raffaelloplayer/login.php", params={"username": username, "password": encrpassword})
	return r.json()

def getprofile(token, userid):
	r = requests.get("https://www.raffaellodigitale.it/media/raffaelloplayer/getprofile.php", params={"userId": userid, "userToken": token})
	if r.status_code != 200:
		return False
	else:
		return r.json()

def getlibrary(token, userid):
	r = requests.get("https://www.raffaellodigitale.it/media/raffaelloplayer/getcatalog_v7.php", params={"userId": userid, "userToken": token})
	return r.json()

def getcover(url):
	r = requests.get(url)
	return r.content

def getsplash(basepath, projectid):
	r = requests.get(basepath + str(projectid) + "/splash.xml")
	return r.text

def getbookinfo(basepath, projectid, ebookid):
	r = requests.get(basepath + str(projectid) + "/book_" + str(ebookid) + "/xml/book1.xml")
	return r.text

def getpagepng(basepath, projectid, ebookid, data):
	r = requests.get(basepath + str(projectid) + "/book_" + str(ebookid) + "/pages/" + str(data) + ".png")
	return r.content

def encryptpassword(password):
	cipher = AES.new(pwdkey.encode(), AES.MODE_CBC, pwdiv.encode())
	bsize = AES.block_size
	padding = (bsize - len(password) % bsize) % bsize * b"\0"
	encrpwd = cipher.encrypt(password.encode() + padding)
	return b64encode(encrpwd).decode()

def decryptpassword(encrpassword):
	cipher = AES.new(pwdkey.encode(), AES.MODE_CBC, pwdiv.encode())
	password = cipher.decrypt(b64decode(encrpassword))
	return password.rstrip(b"\0").decode()

def login(username, password):
	data = getlogindata(username, encryptpassword(password))
	token, userid = data["token"], data["id"]
	return token + "|" + userid

def checktoken(token):
	split = token.split("|")
	if len(split) != 2:
		return False
	stoken, userid = split
	return bool(getprofile(stoken, userid))

def library(token):
	stoken, userid = token.split("|")
	library = getlibrary(stoken, userid)
	books = {}
	for i in library["categories"]:
		for j in i["items"]:
			if not j["userActive"] and not config.getboolean(service, "IncludeNotActivated", fallback=False):
				continue
			books[str(j["id"])] = {"title": j["name"]}
			if "cover" in j:
				books[str(j["id"])]["cover"] = j["cover"]
	return books

def cover(token, bookid, data):
	if "cover" in data:
		return getcover(url)
	else:
		return b""

def downloadbook(token, bookid, data, progress):
	pdf = fitz.Document()
	toc = []
	labels = []

	stoken, userid = token.split("|")
	progress(1, "Getting book info")
	library = getlibrary(stoken, userid)

	book = next(j for i in library["categories"] for j in i["items"] if str(j["id"]) == bookid)
	basepath = book["projectBasePath"]

	secnum = len(book["subProjects"])
	sectionwidth = 97 / secnum
	for i, project in enumerate(book["subProjects"]):
		projectid = project["projectId"]
		toc.append([1, project["projectTitle"], len(pdf) + 1])

		progress(1 + sectionwidth * i, f"Processing section {i + 1}/{secnum}")
		splash = et.fromstring(getsplash(basepath, projectid))
		elements = splash.find("slide").find("elementi")
		if elements.get("url") == "ebook":
			ebookid = elements.get("codice")
		else:
			continue
		bookinfo = et.fromstring(getbookinfo(basepath, projectid, ebookid))
		pages = bookinfo.find("pages").findall("page")
		for j, page in enumerate(pages):
			progress(1 + sectionwidth * i + sectionwidth/10 + (sectionwidth * 9/10) * j/len(pages), f"Downloading page {j + 1}/{len(pages)}")
			pagepng = getpagepng(basepath, projectid, ebookid, page.get("data"))
			img = fitz.open(stream=pagepng, filetype="png")
			pdfbytes = img.convert_to_pdf()
			pdf.insert_pdf(fitz.open(stream=pdfbytes, filetype="pdf"))

			labels.append(page.get("number"))

	progress(98, "Applying toc/labels")
	pdf.set_toc(toc)
	pdf.set_page_labels(lib.generatelabelsrule(labels))
	return pdf
