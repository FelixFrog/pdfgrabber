'''
DISCLAIMER: This file is outdated. The kitaboo webreader has been updated to version 6.0.
This means that this script is completely obsolete, and has become so in a matter of weeks
For this reason it won't be updated anymore. I can't keep up with the webreader updates.
Please, if you need zanichelli books log in with your credentials in the znc script.
It produces much better output and will be supported in the future.

This file will be left here as a cautinary tale for future developers.
'''

'''
import requests
from Crypto.Cipher import Blowfish
from Crypto.Util.Padding import unpad
from base64 import b64decode, b64encode
from zipfile import ZipFile
from tempfile import TemporaryDirectory
from io import BytesIO
import xml.etree.ElementTree as et
from pathlib import Path
from playwright.sync_api import sync_playwright
import lib
import re
import gzip
import fitz

service = "ktb"
urlmatch = r"https?://my\.zanichelli\.it/kitaboo/[0-9a-f]{32}/?"

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

def getoutline(tree, appended, level):
	subtoc = []
	href = tree.get("href")
	if href in appended:
		if tree.get("feild2"):
			subtoc.append([level, tree.get("feild2") + " - " + tree.get("title"), appended.index(href) + 1])
		else:
			subtoc.append([level, tree.get("title"), appended.index(href) + 1])
	for i in tree.findall("node"):
		subtoc.extend(getoutline(i, appended, level + 1))
	return subtoc

def downloadbook(url, progress):
	pdf = fitz.Document()
	toc = []
	labels = []

	index = requests.get(url, allow_redirects=False)
	location = index.headers["Location"]
	if "usertoken" not in location or "bookID" not in location:
		return

	usertoken0 = re.search(r"(?<=\?|&)usertoken=([A-Za-z0-9+/=]+)(?=&|$)", location).group(1)
	bookid0 = re.search(r"(?<=\?|&)bookID=([0-9]+)(?=&|$)", location).group(1)

	progress(1, "Vaidating token")
	tokenvalidation = requests.get("https://zanichelliservices.kitaboo.eu/DistributionServices/services/api/reader/user/123/pc/validateUserToken", params={"usertoken": usertoken0}).json()
	usertoken = tokenvalidation["userToken"]

	progress(2, "Getting info")
	bookdetails = requests.get("https://zanichelliservices.kitaboo.eu/DistributionServices/services/api/reader/distribution/123/pc/book/details", params={"bookID": bookid0}, headers={"usertoken": usertoken}).json()
	# TODO: choose a better selection method
	book = bookdetails["bookList"][0]
	if book["encryption"]:
		print("Encrypted books unsupported!")
		return

	title = book["book"]["title"] + (" - " + book["book"]["description"] if book["book"]["description"] else "")
	bookid, isbn = str(book["book"]["id"]), book["book"]["isbn"]
	progress(3, "Fetching packs")
	resources =  requests.get(f"https://zanichelliservices.kitaboo.eu/DistributionServices/services/api/reader/book/1234/PC/{bookid}/fetchPackages", headers={"usertoken": usertoken}).json()
	resmap = {i["chapterName"]: i["url"] for i in resources["files"]}

	def downloadresource(path, progress=False, total=0, done=0):
		r = requests.get(resmap[path], stream=bool(progress))
		if progress:
			length = int(r.headers.get("content-length", 1))
			file = b""
			for data in r.iter_content(chunk_size=102400):
				file += data
				progress(round(done + len(file) / length * total))
			return file if r.status_code == 200 else False
		else:
			return r.content if r.status_code == 200 else False

	progress(5, "Downloading base.zip")
	baseresource = downloadresource("base.zip", progress, 5, 5)
	baseresource = ZipFile(BytesIO(baseresource))
	base = et.fromstring(baseresource.read("OPS/book_toc.xml").decode())
	pagesmap = {i.get("folioNumber"): i.get("src") for i in sorted(base.find("pages").findall("page"), key=lambda i: int(i.get("sequenceNumber")))}

	appended = list()

	with TemporaryDirectory(prefix="kitaboo.", ignore_cleanup_errors=True) as tmpname:
		tmpdir = Path(tmpname)
		basefiles = ["css", "images", "js", "fonts"]
		baseresource.extractall(tmpdir, [file for file in baseresource.namelist() if any(file.startswith("OPS/" + x) for x in basefiles)])

		with sync_playwright() as p:
			browser = p.chromium.launch()
			bpage = browser.new_page()
			chapters = base.find("chapters").findall("chapter")
			unitwidth = (93 - 10) / len(chapters)
			for off, i in enumerate(chapters):
				unitstart = 10 + (off * unitwidth)
				progress(unitstart, f"Downloading unit {off + 1}/{len(chapters)}")
				chapter = downloadresource(i.find("chapterPagesFile").text, progress, unitwidth / 4, unitstart)
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
					labels.append(page)
					appended.append(pagefile)

					fullpath = tmpdir / "OPS" / pagefile
					sizematch = re.search(r'content\s?=\s?\"([\d\.]+?):([\d\.]+?):([\d\.]+?):([\d\.]+?)\"', open(fullpath, encoding="utf-8").read())
					if sizematch != None:
						width, height = str(float(sizematch.group(3)) - float(sizematch.group(1))), float(sizematch.group(4)) - float(sizematch.group(2))
					#sizematch = re.search('content.+?width\s{,1}=\s{,1}([0-9]+).+?height\s{,1}=\s{,1}([0-9]+)', open(fullpath, encoding="utf-8").read())
					#print(sizematch.group(0), width, height)

					bpage.goto(fullpath.as_uri())
					progress(round(unitstart + unitwidth / 4 + pagewidth * j), f"Rendering page {j + 1}/{len(pages)}")
					pdfpagebytes = bpage.pdf(print_background=True, width=str(width) + "px", height=str(height) + "px", page_ranges="1")
					pagepdf = fitz.Document(stream=pdfpagebytes, filetype="pdf")
					pdf.insert_pdf(pagepdf)
			browser.close()

	tocobj = et.fromstring(baseresource.read("OPS/toc.xml").decode())
	for i in tocobj.find("toc").findall("node"):
		toc.extend(getoutline(i, appended, 1))

	progress(98, "Applying toc/labels")
	if labels:
		pdf.set_page_labels(lib.generatelabelsrule(labels))
	pdf.set_toc(toc)

	return pdf, isbn, title
'''
