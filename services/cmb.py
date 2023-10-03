from Crypto.Cipher import AES
from Crypto.Protocol.KDF import PBKDF2
from Crypto.Hash import SHA1
from Crypto.Util.Padding import unpad
from base64 import b64decode
from itertools import cycle
from zipfile import ZipFile
from tempfile import TemporaryDirectory
from io import BytesIO
import xml.etree.ElementTree as et
from pathlib import Path
from playwright.sync_api import sync_playwright
import re
import requests
import fitz
import time
import lib

key = b"thisIsASecretKey"
salt_and_iv = b"humhanhindustani"
magic = b"OPCPLT_V001"

def getlogindata(username, password, deviceid):
	r = requests.post("https://elevate.cambridge.org/OpenpageServices/BookService.svc/user/login/", json={"userName": username, "password": password, "deviceId": deviceid, "isGoUser": False})
	if r.status_code != 200:
		return
	else:
		r.encoding = "utf-8-sig"
		return r.json()

def getlibrary(accesstoken, userid):
	r = requests.post("https://elevate.cambridge.org/OpenpageServices/BookService.svc/user/" + userid + "/bookshelf/", json={"books": []}, headers={"accessToken": accesstoken})
	if r.status_code != 200:
		return
	else:
		r.encoding = "utf-8-sig"
		return r.json()

def downloadfile(url, progress, total, done):
	r = requests.get(url, stream=True, headers={"Referer": "https://elevate.cambridge.org/"})
	length = int(r.headers.get("content-length", 1))
	if r.status_code != 200:
		return
	file = b""
	for data in r.iter_content(chunk_size=102400):
		file += data
		progress(round(done + len(file) / length * total))
	return file

def login(username, password):
	h = SHA1.new()
	h.update(username.encode())
	deviceid = h.hexdigest()[:16]
	logindata = getlogindata(username, password, deviceid)
	if "error" in logindata or not logindata:
		if logindata.get("error") == "1":
			print("Incorrect credentials!")
		else:
			print("Login failed!")
	else:
		userid = str(logindata["userId"])
		if userid == "0":
			print("Unauthorized!")
		else:
			return logindata["accessToken"] + "/" + userid

def cover(token, bookid, data):
	r = requests.get(data["cover"])
	return r.content

def checktoken(token):
	accesstoken, userid = token.split("/")
	library = getlibrary(accesstoken, userid)
	return "error" not in library and bool(library)

def library(token):
	accesstoken, userid = token.split("/")
	library = getlibrary(accesstoken, userid)

	books = {}
	for i in library["books"]:
		try:
			if time.time() > time.mktime(time.strptime(i["expiry"], "%a %b %d %Y %H:%M:%S.%f UTC")):
				continue
		except ValueError:
			pass
		books[i["id"]] = {"title": i["title"], "cover": i["cover"], "isbn": i["isbn"], "url": i["download_url"], "contentspath": i["package_doc_path"], "key": i["encryptionKey"], "author": i["author"]}

	return books

def downloadbook(token, bookid, data, progress):
	progress(0, "Downloading encrypted epub")
	file = downloadfile(data["url"], progress, 46, 0)
	if not file:
		print("Error in downloading!")
		exit()

	progress(48, "Decrypting")
	startoff = len(file) - (len(magic) + len(str(len(file))))
	magic_off = file.find(magic, startoff)
	enc_start = int(file[magic_off + len(magic):].decode())

	aeskey = bytes([a ^ b for (a, b) in zip(b64decode(data["key"]), cycle(key))])

	key_128 = PBKDF2(aeskey, salt_and_iv, 16, 1000, hmac_hash_module=SHA1)

	enc = file[enc_start:magic_off]

	try:
		cipher = AES.new(key_128, AES.MODE_CBC, salt_and_iv)
		dec = unpad(cipher.decrypt(enc), AES.block_size)
	except ValueError:
		key_256 = PBKDF2(aeskey, salt_and_iv, 32, 1000, hmac_hash_module=SHA1)
		cipher = AES.new(key_256, AES.MODE_CBC, salt_and_iv)
		dec = unpad(cipher.decrypt(enc), AES.block_size)

	borkedzip = bytearray(file[:enc_start] + dec)
	del file

	progress(50, "Fixing headers")
	eocdr_off = len(borkedzip) - 22 # minimum length of EOCDR
	while borkedzip[eocdr_off:eocdr_off + 4] != b"PK\x05\x06": # EOCDR signature
		eocdr_off -= 1

	cdr_size = int.from_bytes(borkedzip[eocdr_off + 12:eocdr_off + 16], byteorder="little")
	cdr_off = int.from_bytes(borkedzip[eocdr_off + 16:eocdr_off + 20], byteorder="little")

	offset = cdr_off

	while borkedzip[offset:offset + 4] == b"PK\x01\x02" and offset < cdr_off + cdr_size:
		tofix = int.from_bytes(borkedzip[offset + 42:offset + 46], byteorder="little")
		borkedzip[tofix:tofix + 4] = b"PK\x03\x04"
		offset += 46 + int.from_bytes(borkedzip[offset + 28:offset + 30], byteorder="little") + int.from_bytes(borkedzip[offset + 30:offset + 32], byteorder="little") + int.from_bytes(borkedzip[offset + 32:offset + 34], byteorder="little")

	bookzip = ZipFile(BytesIO(borkedzip))

	ns = {"opf": "http://www.idpf.org/2007/opf", "dc": "http://purl.org/dc/elements/1.1/", "xhtml": "http://www.w3.org/1999/xhtml", "ops": "http://www.idpf.org/2007/ops"}
	contentpath = data["contentspath"].removeprefix("/")

	def gentoc(item, level, pages, basedir):
		toc = []
		for li in item.findall("xhtml:li", ns):
			ref = li.find("xhtml:a", ns)
			text, href = ref.text, ref.get("href")
			if href.startswith("https://") or href.startswith("http://") or not href:
				continue
			href = (basedir / href.split("#")[0]).resolve()
			toc.append([level, text, pages.index(href) + 1])
			if sub := li.find("xhtml:ol", ns):
				toc.extend(gentoc(sub, level + 1, pages, basedir))
		return toc

	fitz.TOOLS.mupdf_display_errors(False)
	pdf = fitz.Document()
	toc, labels, pages = [], [], []

	with TemporaryDirectory(prefix="cambridge.", ignore_cleanup_errors=True) as tmpname:
		progress(52, "Extracting zip")
		tmpdir = Path(tmpname)
		bookzip.extractall(tmpdir)
		basepath = (tmpdir / contentpath).parent

		contents = et.fromstring(open(tmpdir / contentpath, "r", encoding="utf-8-sig").read())

		files = {i.get("id"): i.attrib for i in contents.find("opf:manifest", ns).findall("opf:item", ns)}
		spine = contents.find("opf:spine", ns)
		pages = [(basepath / files[i.get("idref")]["href"]).resolve() for i in spine.findall("opf:itemref", ns)]
	
		navpath = basepath / next(i["href"] for i in files.values() if i.get("properties") == "nav")
		tocfile = et.fromstring(open(navpath, "r", encoding="utf-8-sig").read())
		tocitem = next(i for i in tocfile.find("xhtml:body", ns).findall("xhtml:nav", ns) if i.get("{http://www.idpf.org/2007/ops}type") == "toc")
		toc.extend(gentoc(tocitem.find("xhtml:ol", ns), 1, pages, navpath.parent))

		labelsdict = {}
		pagelistitem = [i for i in tocfile.find("xhtml:body", ns).findall("xhtml:nav", ns) if i.get("{http://www.idpf.org/2007/ops}type") == "page-list"]
		if pagelistitem:
			for i in pagelistitem[0].find("xhtml:ol", ns).findall("xhtml:li", ns):
				ref = i.find("xhtml:a", ns)
				href = ref.get("href")
				if "#" in href:
					href = "#".join(href.split("#")[:-1])
				labelsdict[(navpath.parent / href).resolve()] = ref.text

		with sync_playwright() as p:
			browser = p.chromium.launch()
			page = browser.new_page()
			for j, fullpath in enumerate(pages):
				sizematch = re.search('content.+?width\s?=\s?([0-9]+).+?height\s?=\s?([0-9]+)', open(fullpath, "r", encoding="utf-8-sig").read())

				page.goto(fullpath.as_uri())
				advancement = (j + 1) / len(pages) * 44 + 54
				progress(advancement, f"Printing {j + 1}/{len(pages)}")
				if sizematch:
					width, height = str(int(sizematch.group(1)) / 144) + "in", str(int(sizematch.group(2)) / 144) + "in"
					pdfpagebytes = page.pdf(print_background=True, width=width, height=height, page_ranges="1")
				else:
					print("Liquid page detected!")
					pdfpagebytes = page.pdf(print_background=True, margin={"left": "5mm", "right": "5mm"})
				pagepdf = fitz.Document(stream=pdfpagebytes, filetype="pdf")

				if label := labelsdict.get(fullpath):
					labels.extend([label] * len(pagepdf))
				else:
					labels.extend(list(map(str, list(range(len(pdf) + 1, len(pdf) + 1 + len(pagepdf))))))
				pdf.insert_pdf(pagepdf)
			browser.close()

	progress(98, "Applying toc/labels")
	pdf.set_page_labels(lib.generatelabelsrule(labels))
	pdf.set_toc(toc)
	return pdf
