import requests
from Crypto.Cipher import Blowfish
from Crypto.Util.Padding import unpad
from Crypto.Random import get_random_bytes
from base64 import b64decode, b64encode
from itertools import cycle, zip_longest
from zipfile import ZipFile
from tempfile import TemporaryDirectory
from io import BytesIO
import xml.etree.ElementTree as et
from pathlib import Path
from playwright.sync_api import sync_playwright
import json
import lib
import re
import gzip
import fitz
import config

service = "znc"

xorprivatekey = "VJTP4zAVsLlrpNXXTGV981Tn7zCew0MHD+VkofkRMPcLjLB+w0N/zj02HzPs/4aRDrDSawNqqN2oXH9V36O0vM2CaKH8duGfUhxF+dY3zAGa0UOaKYEZXEMwM0ZqRW7J8Su/gYV8twZQbyRggzl0LpYVhwiSuGnsPYy61qSGfK1PigKneXc3mzGK/0Oct+SL10rTCPHn3zloHmhJdnVFsk8o8CdR78mgg3dLSnEvaIlJppPfhi+qjnA7LUiAxhRxh5XokzOIUn04zyi4gyR2cPCRXpol0qsAf7vi0bzRUvM3TloqjjfLa3lKCOzLWixrYrhNLmu+hFfDik49h1kLVg=="

config = config.getconfig()

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
	r = requests.get("https://booktab-main-api.zanichelli.it/api/v5/books/" + isbn + "/resource/" + path, headers={"Authorization": "Bearer " + token}, stream=progress)
	if progress:
		length = int(r.headers.get("content-length", 1))
		file = b""
		for data in r.iter_content(chunk_size=102400):
			file += data
			progress(round(done + len(file) / length * total))
		return file if r.status_code == 200 else False
	else:
		return r.content if r.status_code == 200 else False

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
	dec = bytes([a ^ b for (a, b) in zip(file, cycle(b64decode(xorprivatekey)))])
	zipfile = ZipFile(BytesIO(dec))
	return zipfile.read(zipfile.namelist()[0])

def decryptsearch(textdata):
	data = textdata.removeprefix("$:$").removesuffix("$:$")
	return b64decode(decrypt(data, b"zanic!@#")).decode()

def getoutline(tree, appended, offset, level):
	subtoc = []
	href = tree.get("href")
	if href in appended:
		if tree.get("feild2"):
			subtoc.append([level, tree.get("feild2") + " - " + tree.get("title"), appended.index(href) + offset])
		else:
			subtoc.append([level, tree.get("title"), appended.index(href) + offset])
	for i in tree.findall("node"):
		subtoc.extend(getoutline(i, appended, offset, level + 1))
	return subtoc

def downloadbooktab3(token, isbn, pdf, toc, labels, progress, encryption, skipfirst):
	newtoc = toc.copy()
	newlabels = labels.copy()

	progress(5, "Downloading info")
	volumeinfo, tocelems, manifest = getbookfiles(token, isbn, encryption)
	resources = [i["path"] for i in manifest["resources"]]

	units = sorted([i for i in volumeinfo.find("volume").find("units").findall("unit") if i.find("resources")], key=lambda unit: unit.find("unitorder").text)
	#units = [i for i in volumeinfo.find("volume").find("units").findall("unit") if i.find("resources")]

	unitwidth = (95 - 5) / len(units)
	for i, unit in enumerate(units):
		if skipfirst and i == 0:
			continue
		btbid, unitid = unit.get("btbid"), unit.get("id")
		basepath = next(j for j in unit.find("resources").findall("resource") if j.get("type") == "base")
		basepath = next(j.text for j in basepath.findall("download") if j.get("device") == "desktop")

		if btbid + "/" + basepath not in resources:
			continue
		progress(5 + i * unitwidth, f"Downloading unit {i + 1}/{len(units)}")
		unitbase = ZipFile(BytesIO(downloadresource(token, isbn, btbid + "/" + basepath, progress, unitwidth, 5 + i * unitwidth)))
		config = unitbase.read(btbid + "/config.xml")
		if encryption:
			config = xordecrypt(config)
		config = et.fromstring(config.decode())

		pageindex = [j.get("btbid") for j in config.find("links").findall("page")]
		if tocelems:
			spineitem = tocelems[unitid]
			newtoc.append([1, spineitem.find("title").text, len(pdf) + pageindex.index(spineitem.get("page")) + 1])
			for j in spineitem.findall("h1"):
				newtoc.append([2, j.find("title").text, len(pdf) + pageindex.index(j.get("page")) + 1])
		else:
			newtoc.append([1, unit.find("displaytitle").text, len(pdf) + 1])

		pdfpath = config.find("content").text
		if not pdfpath.endswith(".pdf"):
			pdfpath += ".pdf"
		fakepath = next(j.text for j in config.find("filesMap").findall("entry") if j.get("key") == pdfpath)
		unitpdf = unitbase.read(btbid + "/" + fakepath)
		if encryption:
			unitpdf = xordecrypt(unitpdf)
		unitpdf = fitz.Document(stream=unitpdf, filetype="pdf")
		pdf.insert_pdf(unitpdf)

		labels = [page.get("id") for page in config.find("links").findall("page")]
		for j, plabel in zip_longest(range(len(unitpdf)), labels):
			if isinstance(j, int):
				if plabel:
					newlabels.append(plabel)
				else:
					start = config.find("pages").text.split("-")[0]
					if start.isdigit():
						newlabels.append(str(j + int(start)))
					else:
						newlabels.append(len(pdf) - len(unitpdf) + j)

	return pdf, newtoc, newlabels

def downloadbooktab_legacy(token, isbn, pdf, toc, labels, progress, version, skipfirst):
	newlabels = labels.copy()
	newtoc = toc.copy()

	progress(5, "Downloading info")
	volumeinfo, spine, manifest = getbookfiles(token, isbn)
	resources = [i["path"] for i in manifest["resources"]]

	units = [item for volumes in volumeinfo.find("volumes").findall("volume") for item in volumes.find("units").findall("unit")]

	prevlen = len(pdf) + 1

	unitwidth = 90 / len(units)
	for i, unit in enumerate(units):
		if skipfirst and i == 0:
			continue
		if unit.get("href") not in resources:
			continue
		if not (unitid := unit.get("id")):
			unitid = unit.get("href").removesuffix(".zip")
		progress(5 + unitwidth * i, f"Downloading unit {i + 1}/{len(units)}")
		resbytes = downloadresource(token, isbn, unit.get("href"), progress, unitwidth, 5 + unitwidth * i)

		unitzip = ZipFile(BytesIO(resbytes))
		config = et.fromstring(unitzip.read(f"{unitid}/config.xml").decode())

		content = config.find("content").text
		if content.endswith(".swf"):
			continue
		if not content.endswith(".pdf"):
			content += ".pdf"
		pdfpath = unitid + "/" + content
		if pdfpath not in unitzip.namelist():
			continue
		prevlen = len(pdf) + 1
		unitpdf = fitz.Document(stream=unitzip.read(pdfpath), filetype="pdf")

		start = int(config.find("pages").text.split("-")[0])
		labels = [page.get("id") for page in config.find("links").findall("page")]
		for j, plabel in zip_longest(range(len(unitpdf)), labels):
			if isinstance(j, int):
				if plabel:
					newlabels.append(plabel)
				else:
					newlabels.append(str(j + start))

		pdf.insert_pdf(unitpdf)

		newtoc.append([1, unit.find("unittitle").text, prevlen])

		# 1.0 and 2.0 books are not supposed have a spine, but I'm not sure
		if spine:
			print("Wow! You found a legacy book with a spine! Amazing! Contact the developer immediatly!")

	return pdf, newtoc, newlabels

def getbookfiles(token, isbn, encryption=False):
	tocelems = []

	volumeinfo = downloadresource(token, isbn, "volume.xml")
	if encryption:
		volumeinfo = xordecrypt(volumeinfo)
	volumeinfo = et.fromstring(volumeinfo.decode())

	spine = downloadresource(token, isbn, "spine.xml")
	if spine:
		spine = et.fromstring(spine.decode())
		tocelems = {i.get("id"): i for i in spine.findall("unit")}

	manifest = getmanifest(token, isbn)

	return volumeinfo, tocelems, manifest

def downloadkitaboo(token, isbn, pdf, toc, labels, progress, skipfirst):
	newtoc = toc.copy()
	newlabels = labels.copy()

	prevlen = len(pdf) + 1

	progress(5, "Downloading base.zip")
	baseresource = downloadresource(token, isbn, "base.zip", progress, 5, 5)
	baseresource = ZipFile(BytesIO(baseresource))
	base = et.fromstring(baseresource.read("OPS/book_toc.xml").decode())
	pagesmap = {i.get("folioNumber"): i.get("src") for i in sorted(base.find("pages").findall("page"), key=lambda i: int(i.get("sequenceNumber")))}

	appended = list()

	with TemporaryDirectory(prefix="kitaboo.", ignore_cleanup_errors=True) as tmpname:
		tmpdir = Path(tmpname)
		basefiles = ["css", "images", "js", "fonts"]
		if config.getboolean(service, "RemoveImages", fallback=True):
			basefiles.remove("images")
		baseresource.extractall(tmpdir, [file for file in baseresource.namelist() if any(file.startswith("OPS/" + x) for x in basefiles)])

		with sync_playwright() as p:
			browser = p.chromium.launch()
			bpage = browser.new_page()
			chapters = base.find("chapters").findall("chapter")
			unitwidth = (93 - 10) / len(chapters)
			for off, i in enumerate(chapters):
				if skipfirst and off == 0:
					continue
				unitstart = 10 + (off * unitwidth)
				progress(unitstart, f"Downloading unit {off + 1}/{len(chapters)}")
				chapter = downloadresource(token, isbn, i.find("chapterPagesFile").text, progress, unitwidth / 4, unitstart)
				chapter = ZipFile(BytesIO(chapter))

				for file in chapter.namelist():
					if "thumbnail" in file:
						continue
					elif file.endswith("xhtml"):
						decpath = tmpdir / file
						decfile = chapter.read(file)
						if not decfile.startswith(b"<?xml"):
							decfile = decrypt(chapter.read(file), getsecret(isbn[:13]))
						open(decpath, "wb").write(decfile)
					elif file.endswith("svgz"):
						decpath = tmpdir / file
						decfile = gzip.decompress(decryptheader(chapter.read(file), getsecret(isbn[:13])))
						open(decpath, "wb").write(decfile)
					else:
						chapter.extract(file, tmpdir)

				pages = i.find("displayPages").text.split(",")
				pagewidth = (unitwidth * 3) / (4 * len(pages))
				for j, page in enumerate(pages):
					pagefile = pagesmap[page]
					newlabels.append(page)
					appended.append(pagefile)

					fullpath = tmpdir / "OPS" / pagefile
					if not fullpath.is_file():
						pdf.new_page(pno=-1)
					else:
						sizematch = re.search('content.+?width\s?=\s?([0-9]+).+?height\s?=\s?([0-9]+)', open(fullpath, encoding="utf-8").read())

						bpage.goto(fullpath.as_uri())
						progress(round(unitstart + unitwidth / 4 + pagewidth * j), f"Rendering page {j + 1}/{len(pages)}")

						# Sometimes during spring 2023 someone changed the default chrome dev tools pdf print command to default to 144 dpi.
						# Playwright (and Selenium as well) still haven't updated this from the previous default of 96 dpi.
						width, height = str(int(sizematch.group(1)) / 144) + "in", str(int(sizematch.group(2)) / 144) + "in"
						pdfpagebytes = bpage.pdf(print_background=True, width=width, height=height, page_ranges="1")
						pagepdf = fitz.Document(stream=pdfpagebytes, filetype="pdf")
						pdf.insert_pdf(pagepdf)
			browser.close()

	tocobj = et.fromstring(baseresource.read("OPS/toc.xml").decode())
	for i in tocobj.find("toc").findall("node"):
		newtoc.extend(getoutline(i, appended, prevlen, 1))

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
		#if bookmetadata and "-" not in isbn and isbn != "9100000000007":
		books[str(isbn)] = {"title": bookmetadata["title"], "format": i["format"], "cover": bookmetadata["cover"], "relatedisbns": i["relatedIsbns"], "version": i["version"]}
		if "encryptionType" in i:
			books[str(isbn)]["encryption"] = i["encryptionType"]
		if config.getboolean(service, "ShowFormat", fallback=False):
			books[str(isbn)]["title"] = i["format"] + " " + i["version"] + " - " + bookmetadata["title"]
	return books

def downloadbook(token, bookid, data, progress):
	pdf = fitz.Document()
	toc = []
	labels = []
	relatedisbns = data["relatedisbns"]

	skipfirst = config.getboolean(service, "SkipFirstChapter", fallback=False)
	progress(0, "Searching for book index")
	if config.getboolean(service, "SearchIndex", fallback=False) and data["format"] != "booktab":
		for isbn in relatedisbns + [bookid]:
			indice = getadditional(isbn, "_02_IND.pdf")
			if indice:
				indicepdf = fitz.Document(stream=indice, filetype="pdf")
				pdf.insert_pdf(indicepdf)
				indexname = config.get(service, "IndexName", fallback="Indice")
				toc.append([1, indexname, 1])
				labels.extend(["Indice"] * len(pdf))
				break
		else:
			skipfirst = False

	if data["format"] == "booktab":
		if data["version"] in ["1.0", "2.0"]:
			pdf, toc, labels = downloadbooktab_legacy(token, bookid, pdf, toc, labels, progress, data["version"], skipfirst)
		else:
			pdf, toc, labels = downloadbooktab3(token, bookid, pdf, toc, labels, progress, data["encryption"], skipfirst)
	else:
		pdf, toc, labels = downloadkitaboo(token, bookid, pdf, toc, labels, progress, skipfirst)

	progress(95, "Searching for backcover")
	if config.getboolean(service, "SearchBackcover", fallback=True):
		for isbn in relatedisbns + [bookid]:
			quarta = getadditional(isbn, "_03_ALT.pdf")
			if quarta:
				quartapdf = fitz.Document(stream=quarta,filetype="pdf")
				pdf.insert_pdf(quartapdf)
				backcovername = config.get(service, "BackcoverName", fallback="Copertina")
				toc.append([1, backcovername, len(pdf)])
				labels.extend(["C" + str(i + 3) for i in range(len(quartapdf))])
				break

	progress(98, "Applying toc/labels")
	if labels:
		pdf.set_page_labels(lib.generatelabelsrule(labels))
	pdf.set_toc(toc)
	return pdf
