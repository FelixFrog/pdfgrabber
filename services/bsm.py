import requests
import umsgpack
import tarfile
from io import BytesIO
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
import fitz
import lib
import config

service = "bsm"

key = bytes.fromhex("1e00b89873139d2104ed501a8bf8689b")

bsmart_baseurl = "https://www.bsmart.it"

config = config.getconfig()

def getlogindata(username, password, baseurl):
	r = requests.post(baseurl + "/api/v5/session", data={"password": password, "email": username})
	return r.json()

def getlibrary(token, baseurl):
	r = requests.get(baseurl + "/api/v5/books", headers={"AUTH_TOKEN": token}, params={"per_page": 1000000, "page_thumb_size": "medium"})
	return r.json()

def getpreactivations(token, baseurl):
	r = requests.get(baseurl + "/api/v5/books/preactivations", headers={"AUTH_TOKEN": token})
	return r.json()

def getbookinfo(token, bookid, revision, operation, baseurl):
	r = requests.get(baseurl + "/api/v5/books/" + str(bookid) + "/" + str(revision) + "/" + operation, headers={"AUTH_TOKEN": token}, params={"per_page": 1000000})
	return r.json()

def downloadpack(url, progress, total, done):
	r = requests.get(url, stream=True)
	length = int(r.headers.get("content-length", 1))
	file = b""
	for data in r.iter_content(chunk_size=102400):
		file += data
		progress(round(done + len(file) / length * total))
	return tarfile.open(fileobj=BytesIO(file))

def cover(token, bookid, data):
	r = requests.get(data["cover"])
	return r.content

def decryptfile(file):
	header = umsgpack.unpackb(file.read(256).rstrip(b"\x00"))

	iv = file.read(16)
	obj = AES.new(key, AES.MODE_CBC, iv)
	dec = obj.decrypt(file.read(header["start"] - 256 - 16))

	return unpad(dec, AES.block_size) + file.read(), header["md5"]

def login(username, password, baseurl=bsmart_baseurl):
	logindata = getlogindata(username, password, baseurl)
	if "auth_token" not in logindata:
		print("Login failed: " + logindata["message"])
	else:
		return logindata["auth_token"]

def checktoken(token, baseurl=bsmart_baseurl):
	test = getlibrary(token, baseurl)
	return "message" not in test

def library(token, baseurl=bsmart_baseurl, service=service):
	books = dict()
	for i in getlibrary(token, baseurl):
		if i["liquid_text"]:
			# Seems like the liquid_text property doesn't refer to the format of the books. Further investigation on the app is required. 
			# As of now, this enables the download of all books
			pass
		books[str(i["id"])] = {"title": i["title"], "revision": i["current_edition"]["revision"], "cover": i["cover"]}

	if config.getboolean(service, "Preactivations", fallback=True):
		for i in getpreactivations(token, baseurl):
			for book in i["books"]:
				if book["liquid_text"]:
					continue
				books[str(book["id"])] = {"title": book["title"], "revision": book["current_edition"]["revision"], "cover": book["cover"]}

	return books

def downloadbook(token, bookid, data, progress, baseurl=bsmart_baseurl):
	revision = data["revision"]
	progress(0, "Getting resources")
	resources = getbookinfo(token, bookid, revision, "resources", baseurl)
	resmd5 = {}
	for i in resources:
		if i["resource_type_id"] != 14:
			continue
		if pdf := next((j for j in i["assets"] if j["use"] == "page_pdf"), False):
			resmd5[pdf["md5"]] = i["id"], i["title"]


	pagespdf, labelsmap = {}, {}
	progress(5, "Fetching asset packs")
	assetpacks = getbookinfo(token, bookid, revision, "asset_packs", baseurl)

	progress(10, "Downloading pdf pages")
	pagespack = downloadpack(next(i["url"] for i in assetpacks if i["label"] == "page_pdf"), progress, 80, 10)

	progress(90, "Decrypting pages")
	for member in pagespack.getmembers():
		file = pagespack.extractfile(member)
		if file:
			output, md5 = decryptfile(file)
			pid, label = resmd5[md5]
			pagespdf[pid] = output
			labelsmap[pid] = label

	pdf = fitz.Document()
	toc, labels = [], []

	progress(95, "Obtaining toc")
	index = getbookinfo(token, bookid, revision, "index", baseurl)

	bookmarks = {i["first_page"]["id"]:i["title"] for i in index if "first_page" in i}
	for i, (pageid, pagepdfraw) in enumerate(sorted(pagespdf.items())):
		pagepdf = fitz.Document(stream=pagepdfraw, filetype="pdf")
		pdf.insert_pdf(pagepdf)
		labels.append(labelsmap[pageid])
		if pageid in bookmarks:
			toc.append([1, bookmarks[pageid], i + 1])

	progress(98, "Applying toc/labels")
	pdf.set_page_labels(lib.generatelabelsrule(labels))
	pdf.set_toc(toc)
	return pdf
