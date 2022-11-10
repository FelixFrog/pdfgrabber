from Crypto.Signature import PKCS1_v1_5 as PKCS1_v1_5_sig
from Crypto.Cipher import PKCS1_v1_5 as PKCS1_v1_5_ciph
from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import unpad
from Crypto.Hash import HMAC, SHA256
from Crypto.PublicKey import RSA
from Crypto.Cipher import AES
from playwright.sync_api import sync_playwright
from tempfile import TemporaryDirectory
from base64 import b64encode, b64decode
from zipfile import ZipFile
from pathlib import Path
from io import BytesIO
import xml.etree.ElementTree as et
import requests
import string
import random
import time
import json
import fitz
import lib
import re

# It probabily is such a happy time to maintain this pearson's legacy codebase
clientid = "cGnFEyiajGgv2EhcShCPBa7jqwSFpSG5"
hawkkeyid = "GPgRTj6fOI"
hawkkey = "UTpkeCcbmFwsz0DAGZRhnkGuQGoYVz6a"
appid = "54c89f6c1d650fdeccbef5cd"
tenantid = "0a0e20af-1ef3-4650-8f44-48c3bc5f9584"
tenantkey = "9edbf937-3955-4c98-a698-07718a6380df"
rpluszipkey = "sDkjhfkj8yhn8gig"

def getetexttoken(username, password):
	r = requests.post("https://login.pearson.com/v1/piapi/login/webcredentials", data={"password": password, "isMobile": "true", "grant_type": "password", "client_id": clientid, "username": username}, headers={"User-Agent": "mobile_app"})
	return r.json()

def refreshetexttoken(refreshtoken):
	r = requests.post("https://login.pearson.com/v1/piapi/login/webcredentials", data={"refresh": "true", "client_id": clientid, "isMobile": "true"}, cookies={"PiAuthSession": refreshtoken})
	return r.json()

def getetextuserinfo(userid, token):
	r = requests.get(f"https://marin-api.prd-prsn.com/api/1.0/users/{userid}", params={"include": "gpsSubscriptions"}, headers={"Authorization": f"Bearer {token}"})
	return r.json()

def getrplustoken(username, firstname, lastname):
	r = requests.post("https://api-prod.gls.pearson-intl.com/user/session/token", headers={"Authorization": gethawk()}, data={"username": username, "firstname": firstname, "lastname": lastname})
	return r.json()

def getrplususerinfo(rplustoken):
	r = requests.get("https://api-prod.gls.pearson-intl.com/user", headers={"token": rplustoken, "appid": appid})
	return r.json()

def getbookshelf(etexttoken, rplustoken, rplususerid):
	r = requests.get("https://marin-api.prd-prsn.com/api/1.0/rplus/bookshelf", headers={"Authorization": f"Bearer {etexttoken}", "X-Tenant-Id": tenantid, "X-Tenant-Key": tenantkey, "X-Tenant-Region": "IRE", "X-GAB-Authorization": rplustoken, "X-GAB-UserId": rplususerid})
	return r.json()

def getcdntoken(etexttoken, bookid):
	r = requests.get(f"https://marin-api.prd-prsn.com/api/1.0/products/{bookid}/token", headers={"Authorization": f"Bearer {etexttoken}"})
	return r.json()

def getddk(etexttoken, deviceid):
	r = requests.get(f"https://marin-api.prd-prsn.com/api/1.0/capi/ddk/device/{deviceid}", headers={"Authorization": f"Bearer {etexttoken}"})
	return r.json()

def getbookinfo(etexttoken, xsignature, bookid, deviceid):
	data = {"entitlementSource": "RUMBA", "deviceId": deviceid, "bookId": bookid}
	r = requests.post("https://marin-api.prd-prsn.com/api/1.0/capi/product", data=data, headers={"Authorization": f"Bearer {etexttoken}", "X-Signature": xsignature})
	return r.json()

def getcontenttoc(etexttoken, bookid):
	r = requests.get("https://prism.pearsoned.com/api/contenttoc/v1/assets", headers={"Authorization": f"Bearer {etexttoken}", "X-Authorization": etexttoken}, params={"productId": bookid})
	return r.json()

def downloadfile(url, progress, total, done, cdntoken=""):
	r = requests.get(url, headers={"etext-cdn-token": cdntoken} if cdntoken else {}, stream=True)
	length = int(r.headers.get("content-length", 1))
	file = b""
	for data in r.iter_content(chunk_size=102400):
		file += data
		progress(round(done + len(file) / length * total))
	return file

def getrsakey(key):
	# The keys are base64 decoded twice
	decoded = b64decode(b64decode(key).decode())
	return RSA.importKey(decoded)

def computexsignature(devicephrase, signatureddk):
	rsakey = getrsakey(signatureddk)
	message = devicephrase.encode()
	sha = SHA256.new()
	sha.update(devicephrase.encode())

	signer = PKCS1_v1_5_sig.new(rsakey)
	signature = signer.sign(sha)
	return b64encode(signature).decode()

def computedecryptionkey(securedkey, ddk):
	rsakey = getrsakey(ddk)
	message = b64decode(securedkey)

	sentinel = b64encode(get_random_bytes(16))

	cipher = PKCS1_v1_5_ciph.new(rsakey)
	finalkey = cipher.decrypt(message, sentinel, expected_pt_len=24)
	return finalkey

def decryptfile(file, key):
	iv = file[:16]

	# It's not AES128 key=b64decoded string, it's AES192 key=24-byte string
	obj = AES.new(key, AES.MODE_CBC, iv)
	return obj.decrypt(file[16:])

def getoutlines(item, labels, level):
	subtoc = []
	subtoc.append([level, item["title"], labels.index(item["pageno"]) + 1])
	if "children" in item:
		for i in item["children"]:
			subtoc.extend(getoutlines(i, labels, level + 1))
	return subtoc

def zippassword(encryptedpass):
	cipher = AES.new(rpluszipkey.encode(), AES.MODE_CBC, bytes(16))
	return unpad(cipher.decrypt(b64decode(encryptedpass)), AES.block_size)

def gethawkmac(ts, nonce):
	normalizedstring = f"hawk.1.header\n{ts}\n{nonce}\nPOST\n/user/session/token\napi-prod.gls.pearson-intl.com\n443\n\n\n"

	secret = hawkkey.encode()
	h = HMAC.new(secret, digestmod=SHA256)
	h.update(normalizedstring.encode())
	return b64encode(h.digest()).decode()

def gethawk():
	ts = str(int(time.time()))
	nonce = "".join([random.choice(string.ascii_letters) for i in range(6)])
	mac = gethawkmac(ts, nonce)

	return f'ReaderPlus key="{hawkkeyid}", ts="{ts}", nonce="{nonce}", mac="{mac}"'

def cover(token, bookid, data):
	etexttoken, etextuserid, rplustoken, rplususerid, refreshtoken = tuple(token.split("|"))
	if data["type"] == "ETEXT_PDF":
		cdntokenanswer = getcdntoken(etexttoken, bookid)
		r = requests.get(data["cover"], headers={"etext-cdn-token": cdntokenanswer["value"]})
		return r.content
	else:
		r = requests.get(data["cover"])
		return r.content

def refreshtoken(token):
	etexttoken, etextuserid, rplustoken, rplususerid, refreshtoken = tuple(token.split("|"))
	refresh = refreshetexttoken(refreshtoken)
	if "error" not in refresh:
		etexttoken, refreshtoken = refresh["data"]["access_token"], refresh["data"]["refresh_token"]
	etextuserinfo = getetextuserinfo(etextuserid, etexttoken)
	rplususerinfo = getrplususerinfo(rplustoken)
	if "error" not in etextuserinfo and "error" not in rplususerinfo:
		return "|".join([etexttoken, etextuserid, rplustoken, rplususerid, refreshtoken])

def checktoken(token):
	etexttoken, etextuserid, rplustoken, rplususerid, refreshtoken = tuple(token.split("|"))
	etextuserinfo = getetextuserinfo(etextuserid, etexttoken)
	rplususerinfo = getrplususerinfo(rplustoken)
	if "error" not in etextuserinfo and "error" not in rplususerinfo:
		return "|".join([etexttoken, etextuserid, rplustoken, rplususerid, refreshtoken])

def login(username, password):
	logindata = getetexttoken(username, password)
	if "data" not in logindata:
		return
	etexttoken, etextuserid = logindata["data"]["access_token"], logindata["data"]["userId"]
	etextuserinfo = getetextuserinfo(etextuserid, etexttoken)
	if "id" not in etextuserinfo:
		return
	rplustoken = getrplustoken(username, etextuserinfo["firstName"], etextuserinfo["lastName"])
	rplususerinfo = getrplususerinfo(rplustoken["token"])

	return "|".join([etexttoken, etextuserid, rplustoken["token"], rplususerinfo["id"], logindata["data"]["refresh_token"]])

def library(token):
	etexttoken, etextuserid, rplustoken, rplususerid, refreshtoken = tuple(token.split("|"))
	books = {}
	for i in getbookshelf(etexttoken, rplustoken, rplususerid):
		books[str(i["book_id"])] = {"title": i["book_title"], "cover": i["cover_image_url"], "isbn": i["isbn"], "type": i["product_model"], "prodid": i["product_id"], "author": i["author"], "pwd": i["encrypted_password"], "url": i["downloadUrl"]}
	
	return books

def downloadetextbook(etexttoken, bookid, progress):
	decodedjwt = json.loads(b64decode(etexttoken.split(".")[1] + "=="))
	deviceid = decodedjwt["deviceid"]

	progress(0, "Getting ddk")
	keys = getddk(etexttoken, deviceid)
	progress(2, "Computing X-Signature header")
	xsignature = computexsignature(keys["devicePhrase"], keys["signature-ddk"])
	progress(5, "Getting book info")
	bookinfo = getbookinfo(etexttoken, xsignature, bookid, deviceid)
	progress(7, "Downloading encrypted book")
	book = downloadfile(bookinfo["packageUrl"], progress, 81, 7, bookinfo["cdnToken"])
	i = 1
	while not book:
		progress(7, f"Downloading, try #{i}")
		book = downloadfile(bookinfo["packageUrl"], progress, 81, 7, bookinfo["cdnToken"])
		i += 1
	progress(88, "Computing decryption key")
	key = computedecryptionkey(bookinfo["securedKey"], keys["ddk"])
	progress(91, "Decrypting file")
	decryptedbook = decryptfile(book, key)

	progress(93, "Opening pdf")
	pdf = fitz.Document(stream=decryptedbook, filetype="pdf")
	
	progress(95, "Fetching toc")
	tocobj = getcontenttoc(etexttoken, bookid)
	toc = []

	labels = [page.get_label() for page in pdf]
	for i in tocobj["children"]:
		if i["type"] in ["slate", "chapter"]:
			toc.extend(getoutlines(i, labels, 1))

	progress(98, "Applying toc")
	pdf.set_toc(toc)
	return pdf

def downloadrpluspdf(url, password, progress):
	progress(2, "Downloading zip")
	bookzip = ZipFile(BytesIO(downloadfile(url, progress, 95, 2)))

	progress(98, "Extracting book")
	finalpassword = zippassword(password)
	pdfpath = next(i for i in bookzip.namelist() if i.endswith(".pdf"))
	pdf = fitz.Document(stream=bookzip.read(pdfpath, pwd=finalpassword), filetype="pdf")

	return pdf

def gentoc(item, level, pages, basedir):
	toc = []
	for li in item.findall("{http://www.w3.org/1999/xhtml}li"):
		ref = li.find("{http://www.w3.org/1999/xhtml}a")
		text, href = ref.text, ref.get("href")
		if href.startswith("https://") or href.startswith("http://") or not href:
			continue
		href = (basedir / href.split("#")[0]).resolve()
		toc.append([level, text, pages.index(href) + 1])
		if sub := li.find("{http://www.w3.org/1999/xhtml}ol"):
			toc.extend(gentoc(sub, level + 1, pages, basedir))
	return toc

def downloadrplusepub(url, password, progress):
	pdf = fitz.Document()
	toc, labels, pages = [], [], []

	progress(2, "Downloading zip")
	bookzip = ZipFile(BytesIO(downloadfile(url, progress, 20, 2)))
	finalpassword = zippassword(password)

	with TemporaryDirectory(prefix="rplusepub.", ignore_cleanup_errors=True) as tmpdirfull:
		tmpdir = Path(tmpdirfull)
		ns = {"xhtml": "http://www.w3.org/1999/xhtml", "ops": "http://www.idpf.org/2007/ops", "opf": "http://www.idpf.org/2007/opf"}
		progress(24, "Extracting zip")
		epubpath = next(i for i in bookzip.namelist() if i.endswith(".epub"))
		bookzip.extract(epubpath, tmpdir, pwd=finalpassword)
		del bookzip
		epubzip = ZipFile(tmpdir / Path(epubpath))

		progress(31, "Extracting epub")
		epubzip.extractall(tmpdir)
		info = et.fromstring(open(tmpdir / "META-INF" / "container.xml").read())
		contentspath = tmpdir / info.find("{urn:oasis:names:tc:opendocument:xmlns:container}rootfiles").find("{urn:oasis:names:tc:opendocument:xmlns:container}rootfile").get("full-path")
		contents = et.fromstring(open(contentspath).read())

		files = {i.get("id"): i.attrib for i in contents.find("opf:manifest", ns).findall("opf:item", ns)}
		spine = contents.find("opf:spine", ns)
		pages = [(contentspath.parent / files[i.get("idref")]["href"]).resolve() for i in spine.findall("opf:itemref", ns)]
		navpath = contentspath.parent / next(i["href"] for i in files.values() if i.get("properties") == "nav")
		
		tocfile = et.fromstring(open(navpath, "r").read())

		tocitem = next(i for i in tocfile.find("xhtml:body", ns).findall("xhtml:nav", ns) if i.get("{http://www.idpf.org/2007/ops}type") == "toc")
		toc.extend(gentoc(tocitem.find("xhtml:ol", ns), 1, pages, navpath.parent))

		pagelistitem = next(i for i in tocfile.find("xhtml:body", ns).findall("xhtml:nav", ns) if i.get("{http://www.idpf.org/2007/ops}type") == "page-list")
		labelsdict = {}
		for i in pagelistitem.find("xhtml:ol", ns).findall("xhtml:li", ns):
			ref = i.find("xhtml:a", ns)
			labelsdict[(navpath.parent / ref.get("href")).resolve()] = ref.text

		with sync_playwright() as p:
			browser = p.chromium.launch()
			page = browser.new_page()
			for j, fullpath in enumerate(pages):
				if label := labelsdict.get(fullpath):
					labels.append(label)
				else:
					labels.append(str(j + 1))

				sizematch = re.search('content.+?width\s{,1}=\s{,1}([0-9]+).+?height\s{,1}=\s{,1}([0-9]+)', open(fullpath).read())

				page.goto(fullpath.as_uri())
				advancement = (j + 1) / len(pages) * 62 + 36
				progress(advancement, f"Printing {j + 1}/{len(pages)}")
				pdfpagebytes = page.pdf(print_background=True, width=sizematch.group(1) + "px", height=sizematch.group(2) + "px", page_ranges="1")
				pagepdf = fitz.Document(stream=pdfpagebytes, filetype="pdf")
				pdf.insert_pdf(pagepdf)
			browser.close()

	progress(98, "Applying toc/labels")
	pdf.set_page_labels(lib.generatelabelsrule(labels))
	pdf.set_toc(toc)
	return pdf

def downloadbook(token, bookid, data, progress):
	etexttoken, etextuserid, rplustoken, rplususerid, refreshtoken = tuple(token.split("|"))

	match data["type"]:
		case "ETEXT_PDF":
			pdf = downloadetextbook(etexttoken, bookid, progress)
		case "RPLUS_PDF":
			pdf = downloadrpluspdf(data["url"], data["pwd"], progress)
		case "RPLUS_EPUB":
			pdf = downloadrplusepub(data["url"], data["pwd"], progress)
		case _:
			print(f"Unsupported format {data['type']}! Contact the developer to get it added!")
			exit()

	return pdf