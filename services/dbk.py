import requests
import json
from base64 import b64decode
import fitz
from Crypto.Cipher import AES
from Crypto.Util.Padding import unpad

service = "dbk"

pdfpass = "k&WV@E0%Ip6c2WiWG&#R"
iv = bytes([212, 74, 162, 145, 168, 220, 9, 234, 9, 105, 102, 73, 229, 143, 143, 196])
key = bytes([56, 26, 216, 123, 149, 118, 117, 113, 80, 154, 70, 160, 94, 13, 238, 56, 151, 101, 227, 245, 56, 150, 211, 35, 255, 62, 12, 171, 34, 254, 237, 105])

def getlogindata(username, password):
	r = requests.post("https://www.skinbooks.it//auth", json={"username": username, "password": password})
	return r.json()

def getlibrary(token):
	r = requests.get("https://www.skinbooks.it//bookslist", headers={"Authorization": "JWT " + token})
	return r.json()

def downloadpdf(url, progress, total, done):
	r = requests.get(url, stream=True)
	length = int(r.headers.get("content-length", 1))
	file = b""
	for data in r.iter_content(chunk_size=102400):
		file += data
		progress(round(done + len(file) / length * total))
	return file

def decryptfile(data):
	cipher = AES.new(key, AES.MODE_CBC, iv=iv)
	return unpad(cipher.decrypt(data), AES.block_size)

def cover(token, isbn, data):
	#r = requests.get("https://www.laterza.it/immagini/copertine-big/" + isbn + ".jpg")
	r = requests.get(data["cover"])
	return r.content

def login(username, password):
	logindata = getlogindata(username, password)
	if "access_token" not in logindata:
		print("Login failed: " + logindata["description"])
	else:
		return logindata["access_token"]

def checktoken(token):
	import time
	decodedjwt = json.loads(b64decode(token.split(".")[1] + "=="))
	expiry = int(decodedjwt["exp"])

	return int(time.time()) < expiry

def refreshtoken(token):
	r = requests.get("https://www.skinbooks.it//refresh_auth", headers={"Authorization": "JWT " + token})
	resjson = r.json()
	if "access_token" in resjson:
		return resjson["access_token"]
	else:
		return token

def library(token):
	books = dict()
	library = getlibrary(token)
	for i in library["books"]["libreria"]:
		if i["tipo"] != "pdf":
			continue
		books[str(i["identifier"])] = {"title": i["title"], "cover": i["book_image"]}
	return books

def downloadbook(token, bookid, data, progress):
	progress(0, "Downloading pdf")
	pdfurl = "https://graphiservice.fra1.digitaloceanspaces.com/pdf/" + bookid + ".pdf"
	pdf = fitz.Document(stream=downloadpdf(pdfurl, progress, 98, 0), filetype="pdf")

	progress(98, "Removing password protection")
	if pdf.is_encrypted:
		pdf.authenticate(pdfpass)
	return pdf