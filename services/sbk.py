import requests
import xml.etree.ElementTree as et
from hashlib import md5
from Crypto.Random import get_random_bytes
from io import BytesIO
import re
import fitz
import lib

service = "sbk"

mac_addr_key = bytes.fromhex("d85b74c9fee83bc510533fd2eb3a7f8e")

def getlogindata(username, password):
	r = requests.post("https://app.scuolabook.it/store/public/login", data={"username": username, "password": password})
	return et.fromstring(r.text)

def getlibrary(username, sessionid, idhash):
	r = requests.get("https://app.scuolabook.it/store/public/getHistory", params={"userId": username, "sessionId": sessionid, "deviceToken": gettoken(idhash), "wishlist": 0, "model": "GOOGLE-PIXEL_5", "osAPI": 30, "memClass": 256, "memMax": 345872866, "sdCard": "true", "screenSize": "1920x1080", "screenDPI": 294, "osVersion": 11, "appVersion": "3.4", "plat": "android"})
	r.encoding = "utf-8"
	return et.fromstring(r.text)

def getspine(username, sessionid, idhash, sku):
	r = requests.get("https://app.scuolabook.it/store/public/getSpine", params={"userId": username, "sessionId": sessionid, "deviceToken": gettoken(idhash), "sku": sku, "plat": "android"})
	r.encoding = "utf-8"
	return et.fromstring(r.text)

def getdownloadurl(sessionid, idhash, url):
	r = requests.get(url, params={"version": "3.4", "user_name": sessionid, "device_token": gettoken(idhash)})
	r.encoding = "utf-8"
	return et.fromstring(r.text)

def getsessionstatus(sessionid, username):
	r = requests.get("https://app.scuolabook.it/store/public/isSessionActive", params={"sessionid": sessionid, "email": username})
	r.encoding = "utf-8"
	return et.fromstring(r.text)

def downloadencryptedbook(url, progress, total, done):
	r = requests.get(url, stream=True)
	length = int(r.headers.get("content-length", 1))
	file = bytearray()
	for data in r.iter_content(chunk_size=102400):
		file += data
		progress(round(done + len(file) / length * total))
	return bytearray(file)

def cover(token, bookid, data):
	r = requests.get(data["cover"])
	return r.content

def gettoken(inbytes):
	ran1, ran2 = list(get_random_bytes(2))

	out = bytearray()
	for i, v in enumerate(inbytes):
		out.append((ran1 * (i + 1) + ran2 + v + mac_addr_key[i]) % 256)

	out.extend([ran1, ran2])
	return out.hex()

def untokenize(instr):
	inbytes = bytes.fromhex(instr)
	ran1, ran2 = inbytes[16:]

	out = bytearray()
	for i, v in enumerate(inbytes[:16]):
		out.append((v - ran1 * (i + 1) - ran2 - mac_addr_key[i]) % 256)

	return out

def xrefgen(offset, file):
	offset += 6
	while True:
		end = file.find(b"\r\n", offset)
		yield file[offset:end], offset
		offset = end + 2

def createdeviceidhash(sessionid):
	salted = sessionid.encode() + b"fuckscuolabook"
	#salted = sessionid.encode()
	return md5(salted).digest()

def login(username, password):
	print("WARNING: Scuolabook will cease to operate on 31/12/2023!")
	logindata = getlogindata(username, password)
	errorcode = next(i.text for i in logindata.findall("field") if i.get("name") == "errorCode")
	if errorcode != "0":
		message = next(i.text for i in logindata.findall("field") if i.get("name") == "errorDescription")
		print("Login failed: " + message)
	else:
		return next(i.text for i in logindata.findall("field") if i.get("name") == "sessionId") + "/" + username

def library(token):
	sessionid, username = token.split("/")

	idhash = createdeviceidhash(sessionid)

	books = dict()
	for i in getlibrary(username, sessionid, idhash).findall("book"):
		book = {j.get("name"): j.text for j in i.findall("field")}
		if book["DRMType"] != "drm_pdf":
			continue
		if book["subtitle"]:
			title = book["title"] + " - " + book["subtitle"]
		else:
			title = book["title"]
		books[str(book["bookId"])] = {"title": title, "url": book["bookFileURL"], "cover": book["image700"]}

	return books

def checktoken(token):
	sessionid, username = token.split("/")

	active = getsessionstatus(sessionid, username)
	status = next(i.text for i in active.findall("field") if i.get("name") == "active")
	return status == "true"

def guessmagic(file):
	root = re.search(b"\/Root (\d+) (\d+) R", file)
	refnum = int(root.group(1))
	for objnum, contents in re.findall(b"(\d{,12}) \d{,12} obj(.+?)endobj", file, re.S):
		if b"/Catalog" in contents:
			return int(objnum) ^ refnum

def getoutline(item, level):
	toc = [[level, item.find("title").text, int(item.find("page").text)]]
	for subitem in item.findall("section"):
		toc.extend(getoutline(subitem, level + 1))
	return toc

def downloadbook(token, bookid, data, progress):
	sessionid, username = token.split("/")

	idhash = createdeviceidhash(sessionid)

	progress(0, "Obtaining download url")
	downloadinfo = getdownloadurl(sessionid, idhash, data["url"])

	progress(5, "Downloading DRM protected pdf")
	file = downloadencryptedbook(downloadinfo.find("downloadURL").text, progress, 85, 5)

	progress(90, "Removing DRM")
	key2 = bytes.fromhex(downloadinfo.find("activationKey").text)

	usernamehash = md5(username.encode()).digest()

	usernamehash = int.from_bytes(usernamehash, "big")
	devicehash = int.from_bytes(idhash, "big")
	key2hash = int.from_bytes(key2, "big")

	key3 = usernamehash ^ devicehash ^ key2hash

	n = len(file) & 127
	key4 = bytearray()
	for i in file[11:11 + 42]:
		key4.append(i ^ n)
		n = n + 1 & 127
	magic = key3 % int(key4[26:], 16)

	magic2 = guessmagic(file)
	if magic != magic2:
		# the magic numbers don't match, might be a bug
		pass

	startxref = int(re.search(b"startxref\r\n([0-9]+)", file).group(1))

	cobjn = 0
	for i, xrefoff in xrefgen(startxref, file):
		section = re.fullmatch("([0-9]+) [0-9]+", i.decode())
		reference = re.fullmatch("([0-9]{10}) [0-9]{5} [fn]", i.decode())
		if section:
			cobjn = int(section.group(1))
		elif reference:
			if i == b"0000000000 65535 f":
				cobjn += 1
				continue
			newoffset = int(reference.group(1)) ^ magic
			n = len(str(cobjn ^ magic))
			file[newoffset:newoffset + n] = str(cobjn).zfill(n).encode()
			file[xrefoff:xrefoff + 10] = str(newoffset).zfill(10).encode()
			cobjn += 1
		else:
			break

	progress(95, "Fetching spine")
	spine = getspine(username, sessionid, idhash, bookid)

	fitz.TOOLS.mupdf_display_errors(False)
	pdf = fitz.Document(stream=file, filetype="pdf")

	progress(98, "Applying toc/labels")
	if tocelem := spine.find("sections"):
		toc = []
		for i in tocelem.findall("section"):
			toc.extend(getoutline(i, 1))
		pdf.set_toc([i for i in toc if i[2] <= len(pdf)])
	if spine.find("labels"):
		labels = [v.find("page_label").text for i, v in enumerate(spine.find("labels").findall("label")) if i <= len(pdf)]
		pdf.set_page_labels(lib.generatelabelsrule(labels))

	return pdf
