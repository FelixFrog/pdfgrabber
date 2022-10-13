import requests
from Crypto.Cipher import Blowfish
from Crypto.Util.Padding import unpad
from Crypto.Random import get_random_bytes
from base64 import b64decode, b64encode
from itertools import cycle
from zipfile import ZipFile
from tempfile import TemporaryDirectory
from io import BytesIO
import xml.etree.ElementTree as et
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
import lib
import re
import gzip
import fitz

service = "znc"

xorprivatekey = bytes([84, 148, 207, 227, 48, 21, 176, 185, 107, 164, 213, 215, 76, 101, 125, 243, 84, 231, 239, 48, 158, 195, 67, 7, 15, 229, 100, 161, 249, 17, 48, 247, 11, 140, 176, 126, 195, 67, 127, 206, 61, 54, 31, 51, 236, 255, 134, 145, 14, 176, 210, 107, 3, 106, 168, 221, 168, 92, 127, 85, 223, 163, 180, 188, 205, 130, 104, 161, 252, 118, 225, 159, 82, 28, 69, 249, 214, 55, 204, 1, 154, 209, 67, 154, 41, 129, 25, 92, 67, 48, 51, 70, 106, 69, 110, 201, 241, 43, 191, 129, 133, 124, 183, 6, 80, 111, 36, 96, 131, 57, 116, 46, 150, 21, 135, 8, 146, 184, 105, 236, 61, 140, 186, 214, 164, 134, 124, 173, 79, 138, 2, 167, 121, 119, 55, 155, 49, 138, 255, 67, 156, 183, 228, 139, 215, 74, 211, 8, 241, 231, 223, 57, 104, 30, 104, 73, 118, 117, 69, 178, 79, 40, 240, 39, 81, 239, 201, 160, 131, 119, 75, 74, 113, 47, 104, 137, 73, 166, 147, 223, 134, 47, 170, 142, 112, 59, 45, 72, 128, 198, 20, 113, 135, 149, 232, 147, 51, 136, 82, 125, 56, 207, 40, 184, 131, 36, 118, 112, 240, 145, 94, 154, 37, 210, 171, 0, 127, 187, 226, 209, 188, 209, 82, 243, 55, 78, 90, 42, 142, 55, 203, 107, 121, 74, 8, 236, 203, 90, 44, 107, 98, 184, 77, 46, 107, 190, 132, 87, 195, 138, 78, 61, 135, 89, 11, 86])

def getlogindata(username, password):
	logindata = {"username": username, "password": password, "device_id": get_random_bytes(8).hex(), "device_name": "iPhone Grosso (tm)", "dry_run": False}
	r = requests.post("https://booktab-fast-api.zanichelli.it/api/v5/sessions", json=logindata)
	return r.json()

def getmetadata():
	r = requests.get("https://booktab-fast-api.zanichelli.it/api/v5/metadata")
	return r.json()

def getlibrary(token):
	r = requests.get("https://booktab-fast-api.zanichelli.it/api/v5/books", headers={"Authorization": "Bearer " + token})
	return r.json()

def getmanifest(token, isbn):
	r = requests.get("https://booktab-main-api.zanichelli.it/api/v5/books/" + isbn + "/resource/manifest.log", headers={"Authorization": "Bearer " + token})
	return r.json()

def downloadresource(token, isbn, path, progress=False, total=0, done=0):
	showprogress = bool(progress)
	r = requests.get("https://booktab-main-api.zanichelli.it/api/v5/books/" + isbn + "/resource/" + path, headers={"Authorization": "Bearer " + token}, stream=showprogress)
	if showprogress:
		length = int(r.headers.get("content-length", 1))
		file = b""
		for data in r.iter_content(chunk_size=102400):
			file += data
			progress(round(done + len(file) / length * total))
		return file
	else:
		return r.content

def cover(token, bookid, data):
	r = requests.get("https://booktab-main-api.zanichelli.it/" + data["cover"].removesuffix(".png") + "@2x.png")
	return r.content

def checktoken(token):
	r = requests.get("https://booktab-fast-api.zanichelli.it/api/v5/users/me", headers={"Authorization": "Bearer " + token})
	return bool(r.content)

def getadditional(bookid, extratype):
	r = requests.get("https://staticmy.zanichelli.it/catalogo/assets/" + bookid + extratype)
	if r.status_code == 200:
		return r.content

def decrypt(data, key):
	cipher = Blowfish.new(key, Blowfish.MODE_ECB)
	decrypted = cipher.decrypt(b64decode(data))

	return unpad(decrypted, Blowfish.block_size)

def getsecret(key):
	return b64encode((key[-4:] + "zanichelli").encode())[:9]

def decryptheader(infile, key):
	file = BytesIO(infile)
	headerlen = int.from_bytes(file.read(4), byteorder="big")
	header = file.read(headerlen)
	return decrypt(header, key) + file.read()

def xordecrypt(file):
	dec = bytes([a ^ b for (a, b) in zip(file, cycle(xorprivatekey))])
	zipfile = ZipFile(BytesIO(dec))
	return zipfile.read(zipfile.namelist()[0])

def decryptsearch(textdata):
	data = textdata.removeprefix("$:$").removesuffix("$:$")
	return b64decode(decrypt(data, b"zanic!@#")).decode()

def getoutline(tree, appended, offset, level):
	subtoc = []
	if tree.get("feild2"):
		subtoc.append([level, tree.get("feild2") + " - " + tree.get("title"), appended.index(tree.get("href")) + offset])
	else:
		subtoc.append([level, tree.get("title"), appended.index(tree.get("href")) + offset])
	for i in tree.findall("node"):
		subtoc.extend(getoutline(i, appended, offset, level + 1))
	return subtoc

def downloadbooktab(token, isbn, offset, pdf, toc, labels, progress):
	newtoc = toc.copy()
	newlabels = labels.copy()

	progress(5, "Downloading volume.xml")
	volumeinfo = downloadresource(token, isbn, "volume.xml")
	volumeinfo = xordecrypt(volumeinfo)
	volumeinfo = et.fromstring(volumeinfo.decode())

	progress(8, "Downloading spine.xml")
	spine = downloadresource(token, isbn, "spine.xml")
	spine = et.fromstring(spine.decode())
	tocelems = {i.get("btbid"): i for i in spine.findall("unit")}

	pcount = offset + 1
	units = [i for i in volumeinfo.find("volume").find("units").findall("unit") if i.find("resources")]
	unitwidth = (95 - 11) / len(units)
	for i, unit in enumerate(units):
		btbid = unit.get("btbid")
		basepath = next(j for j in unit.find("resources").findall("resource") if j.get("type") == "base")
		basepath = next(j.text for j in basepath.findall("download") if j.get("device") == "desktop")
		progress(11 + i * unitwidth, f"Downloading unit {i + 1}/{len(units)}")
		unitbase = ZipFile(BytesIO(downloadresource(token, isbn, btbid + "/" + basepath, progress, unitwidth, 11 + i * unitwidth)))
		config = xordecrypt(unitbase.read(btbid + "/config.xml"))
		config = et.fromstring(config.decode())

		pdfpath = config.find("content").text + ".pdf"
		fakepath = next(j.text for j in config.find("filesMap").findall("entry") if j.get("key") == pdfpath)
		unitpdf = xordecrypt(unitbase.read(btbid + "/" + fakepath))
		unitpdf = fitz.Document(stream=unitpdf, filetype="pdf")
		pdf.insert_pdf(unitpdf)

		pageindex = [j.get("btbid") for j in config.find("links").findall("page")]
		spineitem = tocelems[btbid]
		newtoc.append([1, spineitem.find("title").text, pcount + pageindex.index(spineitem.get("page"))])
		for j in spineitem.findall("h1"):
			newtoc.append([2, j.find("title").text, pcount + pageindex.index(j.get("page"))])
		pcount += len(unitpdf)

		start = int(config.find("pages").text.split("-")[0])
		for j, page in enumerate(config.find("links").findall("page")):
			if label := page.get("id"):
				newlabels.append(label)
			else:
				newlabels.append(str(j + start))
	return pdf, newtoc, newlabels

def downloadkitaboo(token, isbn, offset, pdf, toc, labels, progress):
	newtoc = toc.copy()
	newlabels = labels.copy()

	progress(5, "Downloading base.zip")
	baseresource = downloadresource(token, isbn, "base.zip", progress, 5, 5)
	baseresource = ZipFile(BytesIO(baseresource))
	base = et.fromstring(baseresource.read("OPS/book_toc.xml").decode())
	pagesmap = {i.get("folioNumber"): i.get("src") for i in sorted(base.find("pages").findall("page"), key=lambda i: int(i.get("sequenceNumber")))}
	newlabels.extend(list(pagesmap))

	appended = list()

	chromeoptions = Options()
	chromeoptions.add_argument("--headless")
	chromeoptions.binary_location = lib.chromebinlocation

	with TemporaryDirectory(prefix="kitaboo.", ignore_cleanup_errors=True) as tmpdir:
		basefiles = ["css", "images", "js", "fonts"]
		baseresource.extractall(tmpdir, [file for file in baseresource.namelist() if any(file.startswith("OPS/" + x) for x in basefiles)])

		with webdriver.Chrome(options=chromeoptions, executable_path=lib.chromedriverlocation) as wd:
			chapters = base.find("chapters").findall("chapter")
			unitwidth = (93 - 10) / len(chapters)
			for off, i in enumerate(chapters):
				unitstart = 10 + (off * unitwidth)
				progress(unitstart, f"Downloading unit {off + 1}/{len(chapters)}")
				chapter = downloadresource(token, isbn, i.find("chapterPagesFile").text, progress, unitwidth / 4, unitstart)
				chapter = ZipFile(BytesIO(chapter))

				for file in chapter.namelist():
					if "thumbnail" in file:
						continue
					elif file.endswith("xhtml"):
						decpath = tmpdir + "/" + file
						decfile = chapter.read(file)
						if not decfile.startswith(b"<?xml"):
							decfile = decrypt(chapter.read(file), getsecret(isbn))
						open(decpath, "wb").write(decfile)
					elif file.endswith("svgz"):
						decpath = tmpdir + "/" + file
						decfile = gzip.decompress(decryptheader(chapter.read(file), getsecret(isbn)))
						open(decpath, "wb").write(decfile)
					else:
						chapter.extract(file, tmpdir)

				pages = i.find("displayPages").text.split(",")
				pagewidth = (unitwidth * 3) / (4 * len(pages))
				for j, page in enumerate(pages):
					pagefile = pagesmap[page]
					appended.append(pagefile)

					fullpath = tmpdir + "/OPS/" + pagefile
					match = re.search('content="width=([0-9]+), height=([0-9]+)"', open(fullpath).read())

					wd.get('file://' + fullpath)
					progress(round(unitstart + unitwidth / 4 + pagewidth * j), f"Rendering page {j + 1}/{len(pages)}")
					b64page = wd.execute_cdp_cmd("Page.printToPDF", {"printBackground": True, "paperWidth": int(match.group(1))/96, "paperHeight": int(match.group(2))/96, "pageRanges": "1", "marginTop": 0, "marginBottom": 0, "marginLeft": 0, "marginRight": 0})
					pagepdf = fitz.Document(stream=b64decode(b64page["data"]), filetype="pdf")
					pdf.insert_pdf(pagepdf)

	progress(93, "Applying toc")
	tocobj = et.fromstring(baseresource.read("OPS/toc.xml").decode())
	for i in tocobj.find("toc").findall("node"):
		newtoc.extend(getoutline(i, appended, offset + 1, 1))

	return pdf, newtoc, newlabels

def login(username, password):
	logindata = getlogindata(username, password)
	if "token" not in logindata:
		print("Login failed: " + logindata["message"])
	else:
		return logindata["token"]

def library(token):
	library = getlibrary(token)
	metadata = getmetadata()

	books = dict()
	for i in library["books"]:
		isbn = i["isbn"]
		bookmetadata = next((j for j in metadata["books"] if j["isbn"] == isbn), False)
		if bookmetadata and "-" not in isbn and isbn != "9100000000007":
			books[str(isbn)] = {"title": bookmetadata["title"], "format": i["format"], "cover": bookmetadata["cover"], "relatedisbns": i["relatedIsbns"]}

	return books

def downloadbook(token, bookid, data, progress):
	pdf = fitz.Document()
	toc = []
	labels = []
	relatedisbns = data["relatedisbns"]
	offset = 0

	progress(0, "Searching for book index")
	if data["format"] != "booktab":
		for isbn in relatedisbns + [bookid]:
			indice = getadditional(isbn, "_02_IND.pdf")
			if indice:
				indicepdf = fitz.Document(stream=indice, filetype="pdf")
				pdf.insert_pdf(indicepdf)
				offset = len(pdf)
				toc.append([1, "Indice dei contenuti", 1])
				labels.extend(["Indice"] * len(pdf))
				break

	if data["format"] == "booktab":
		pdf, toc, labels = downloadbooktab(token, bookid, offset, pdf, toc, labels, progress)
	else:
		pdf, toc, labels = downloadkitaboo(token, bookid, offset, pdf, toc, labels, progress)

	offset = len(pdf) + 1

	progress(95, "Searching for backcover")
	for isbn in relatedisbns + [bookid]:
		quarta = getadditional(isbn, "_03_ALT.pdf")
		if quarta:
			quartapdf = fitz.Document(stream=quarta,filetype="pdf")
			pdf.insert_pdf(quartapdf)
			toc.append([1, "Quarta di copertina", offset])
			labels.extend(["Copertina"] * len(quartapdf))
			break

	progress(98, "Applying toc/labels")
	pdf.set_page_labels(lib.generatelabelsrule(labels))
	pdf.set_toc(toc)
	return pdf