from zipfile import ZipFile
from io import BytesIO
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad
import zlib
import re
import fitz
import requests
import lxml.html

service = "pmb"

xodpassword = "3b00k1nt3r4tt1v0"

def getlibrary():
	r = requests.get("https://www.palumboeditore.it/Biblioteca/Saggi-digitali")
	return r.text

def getxod(url, progress, total, done):
	r = requests.get(url, stream=True)
	length = int(r.headers.get("content-length", 1))
	file = b""
	for data in r.iter_content(chunk_size=102400):
		file += data
		progress(round(done + len(file) / length * total))
	return file

def cover(token, bookid, data):
	r = requests.get(data["cover"])
	return r.content

def login(username, password):
	return "dummy"

def checktoken(token):
	return True

def library(token):
	htmlres = getlibrary()
	page = lxml.html.document_fromstring(htmlres)
	bookparent = page.get_element_by_id("scaffali")

	books = dict()
	for book in bookparent.find_class("libro"):
		title = book.get("title").replace("<br>", "- ").strip()
		link = book.find("a")
		reader = re.search(r"https:\/\/www\.palumboeditore\.it\/Biblioteca\/reader\/d\/(\w+)\/", link.get("onclick"))
		if reader:
			bookid = reader.group(1)
			cover = "https://www.palumboeditore.it" + link.find("img").get("src")
			url = f"https://www.palumboeditore.it/portals/0/libreria/xod/{bookid}.xod"
			books[bookid] = {"title": title, "cover": cover, "url": url}

	return books

def computekey(filename, password):
	key = bytearray(16)
	for i in range(16):
		key[i] = i
		if i < len(password):
			key[i] |= ord(password[i])
		g = len(filename) + i - 16
		if 0 <= g:
			key[i] |= ord(filename[g])
	return key

def downloadbook(token, bookid, data, progress):
	xod = getxod(data["url"], progress, 70, 0)
	progress(70, "Decrypting xod")
	dword = lambda file, off, size: int.from_bytes(file[off:off + size], byteorder="little")

	eocdr_off = len(xod) - 22 # minimum length of EOCDR
	while xod[eocdr_off:eocdr_off + 4] != b"PK\x05\x06": # EOCDR signature
		eocdr_off -= 1

	cdr_size = dword(xod, eocdr_off + 12, 4)
	cdr_off = dword(xod, eocdr_off + 16, 4)

	offset = cdr_off

	temp_zip_mem = BytesIO()
	with ZipFile(temp_zip_mem, mode="w") as temp_zip:
		while xod[offset:offset + 4] == b"PK\x01\x02" and offset < cdr_off + cdr_size - 42: # minimum CDR file header size
			progress(70 + round(((offset - cdr_off) / cdr_size) * 25))
			fileoff = dword(xod, offset + 42, 4)
			if xod[fileoff:fileoff + 4] != b"PK\x03\x04":
				#print(f"Corrupt zip, not a local file header at {fileoff}. Skipping...")
				continue
			compression = dword(xod, fileoff + 8, 2)
			size = dword(xod, fileoff + 18, 4)
			filenamelen = dword(xod, fileoff + 26, 2)
			filename = xod[fileoff + 30:fileoff + 30 + filenamelen].decode()
			contentsoff = fileoff + 30 + filenamelen + dword(xod, fileoff + 28, 2)

			if size % AES.block_size != 0 or size < AES.block_size:
				#print(f"Invalid xod, file at {fileoff} is not encrypted. Skipping...")
				continue

			iv = xod[contentsoff:contentsoff + AES.block_size]
			enc_data = xod[contentsoff + AES.block_size:contentsoff + size]
			key = computekey(filename, xodpassword)

			cipher = AES.new(key, AES.MODE_CBC, iv)
			file_data = unpad(cipher.decrypt(enc_data), AES.block_size)

			if compression == 8:
				file_data = zlib.decompress(file_data, -15)

			if filename.startswith("Pages/") and filename.endswith(".xaml"):
				file_data = re.sub(br"<Glyphs.+?UnicodeString=\"www\.pdftron\.com\".+?/>[\n.]*?<Path.+?Data=.+?/>", b"", file_data, count=1)

			temp_zip.writestr(filename, file_data)

			offset += 46 + dword(xod, offset + 28, 2) + dword(xod, offset + 30, 2) + dword(xod, offset + 32, 2)

	progress(96, "Converting xps")
	xps = fitz.open(stream=temp_zip_mem, filetype="xps")
	pdf = fitz.open(stream=xps.convert_to_pdf(), filetype="pdf")
	progress(98, "Applying toc")
	pdf.set_toc(xps.get_toc())
	return pdf
