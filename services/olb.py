from Crypto.Random import get_random_bytes
from Crypto.Util.Padding import unpad
from Crypto.Cipher import AES
from Crypto.Hash import HMAC, SHA256
from base64 import b64encode, b64decode
#import xml.etree.ElementTree as et
from lxml import etree as et
from zipfile import ZipFile
from io import BytesIO
import tempfile
import time
import requests
import re
import fitz

service = "olb"

clientid = "HJ5uk5aEjz590ZnNlj41OtmCQ3psgOQp"
signedsecret = b"MYQYWUFC8GCPEV7N0ZNL5H1PRVUVP"
header = bytes([0, 3, 1, 3, 4, 0, 8, 2, 8, 8])

def base64url(inbytes):
	b64str = b64encode(inbytes).decode()
	return b64str.replace("=", "").replace("+", "-").replace("/", "_")

def getmillisnow():
	return str(round(time.time() * 1000))

def getchallenge():
	verifier = base64url(get_random_bytes(32))

	h = SHA256.new()
	h.update(verifier.encode())
	challenge = base64url(h.digest())
	return verifier, challenge

def login(username, password):
	verifier, challenge = getchallenge()

	s = requests.Session()
	r = s.get("https://id.oup.com/authorize", params={"response_type": "code", "client_id": clientid, "redirect_uri": "https://www.oxfordlearnersbookshelf.com/", "state": b64encode(get_random_bytes(8)).decode(), "scope": "openid email profile offline_access", "code_challenge": challenge, "code_challenge_method": "S256", "audience": "https://prod-oup.eu.auth0.com/api/v2/", "providerId": "OLB_MOBILE"})
	query = dict([i.split("=") for i in r.url.split("?")[1].split("&")])

	r = s.post("https://id.oup.com/usernamepassword/login", json={"client_id": clientid, "redirect_uri": "https://www.oxfordlearnersbookshelf.com/", "tenant": "prod-oup", "response_type": "code", "scope": "openid email profile offline_access", "audience": "https://prod-oup.eu.auth0.com/api/v2/", "state": query["state"], "_intstate": "deprecated", "username": username, "password": password, "connection": "Self-registered-users"}, headers={"Auth0-Client": "eyJuYW1lIjoiYXV0aDAuanMtdWxwIiwidmVyc2lvbiI6IjkuMTMuNCJ9"})
	form = dict(re.findall(r"<input(?=.+?type=['\"]hidden['\"])(?=.+?name=['\"](.*?)['\"]).+?value=['\"](.*?)['\"].*?>", r.text, re.S))
	if "wctx" in form:
		form["wctx"] = form["wctx"].replace("&#34;", "\"")

	r = s.post("https://id.oup.com/login/callback", data=form)
	if "?" not in r.url:
		return
	query = dict([i.split("=") for i in r.url.split("?")[1].split("&")])

	r = requests.post("https://id.oup.com/oauth/token", json={"client_id": clientid, "code": query["code"], "code_verifier": verifier, "grant_type": "authorization_code", "redirect_uri": "https://www.oxfordlearnersbookshelf.com"})
	tokenreq = r.json()
	return tokenreq["id_token"] + "|" + tokenreq["refresh_token"]

def getidentity(idtoken):
	r = requests.post("https://account.oup.com/api/edu/identity", headers={"Authorization": "Bearer " + idtoken}, json={"userId": "null"})
	return r.json()

def getlibrary(identity, idtoken):
	r = requests.get("https://account.oup.com/api/edu/user/" + identity + "/licences/ELT_OLB_MASTER", headers={"Authorization": "Bearer " + idtoken}, params={"returnExternalIds": "true", "platformId": "elt_olb"})
	return r.json()

def getbookinfo(bookid):
	r = requests.get("https://cms.oxfordlearnersbookshelf.com/api/content_info.php", params={"bid": bookid})
	return r.json()

def getrefreshtoken(refreshtoken):
	r = requests.post("https://id.oup.com/oauth/token", json={"grant_type": "refresh_token", "client_id": clientid, "refresh_token": refreshtoken})
	return r.json()

def computexauth(url, secretkey=signedsecret):
	timemillis = getmillisnow()
	h = HMAC.new(secretkey, digestmod=SHA256)
	h.update((url + timemillis).encode())
	return h.hexdigest(), timemillis

def truncateurl(url):
	return "/" + "/".join(url.split("/")[3:])

def getsignedurl(url, xauth, timemillis):
	r = requests.get("https://cms.oxfordlearnersbookshelf.com/api/get-signedurl.php", params={"cdnUrl":url}, headers={"X-Authorization": xauth, "X-Timestamp": timemillis})
	return r.text

def downloadzip(url, tempfile, progress, total, done):
	r = requests.get(url, stream=True)
	length = int(r.headers.get("content-length", 1))
	tot = 0
	for data in r.iter_content(chunk_size=102400):
		tot += tempfile.write(data)
		progress(round(done + tot / length * total))

def refreshtoken(token):
	idtoken, refreshtoken = token.split("|")
	refresh = getrefreshtoken(refreshtoken)
	print(refresh)
	if "error" in refresh:
		return
	else:
		return refresh["id_token"] + "|" # + refresh["refresh_token"]

def getcover(url):
	r = requests.get(url)
	return r.content

def checktoken(token):
	idtoken, refreshtoken = token.split("|")
	identity = getidentity(idtoken)
	return "data" in identity

def decryptfile(data, bid):
	if data[:len(header)] != header:
		return data

	h = SHA256.new()
	h.update(bid.encode())

	cipher = AES.new(h.digest(), AES.MODE_ECB)
	decrypted = cipher.decrypt(data[len(header):]).rstrip(b"\x0b")
	padlength = decrypted[-1]
	if bytes([padlength] * padlength) == decrypted[-padlength:]:
		return decrypted[:-padlength]
	else:
		return decrypted

def parsebook(book):
	if "external" not in book:
		return
	ids = {i["typeId"]: i["id"] for i in book["external"]}
	if "bid" not in ids:
		return
	return {ids["bid"]: {"title": book["productName"], "isbn": ids["isbn"]}}

def library(token):
	idtoken, refreshtoken = token.split("|")
	identity = getidentity(idtoken)

	library = getlibrary(identity["data"]["user"]["userId"], idtoken)

	books = dict()
	for i in library["data"]["licenses"]:
		for j in i["oupLicense"]["productIds"]:
			if "linkedProductIds" not in j:
				book = parsebook(j)
				if book:
					books = books | book
			else:
				for k in j["linkedProductIds"]:
					book = parsebook(k)
					if book:
						books = books | book
	return books

def cover(token, bookid, data):
	bookinfo = getbookinfo(bookid)
	book = bookinfo["msg"]["content_list"][0]
	cover = getcover(book["list_thumbnail"])
	return cover

def downloadbook(token, bookid, data, progress):
	progress(0, "Getting book info")
	bookinfo = getbookinfo(bookid)
	book = bookinfo["msg"]["content_list"][0]

	progress(2, "Signing url")
	xauth, timemillis = computexauth(truncateurl(book["zip_download_url"]))
	signedurl = getsignedurl(book["zip_download_url"], xauth, timemillis)

	return downloadoxfordbook(signedurl, bookid, progress)

def downloadoxfordbook(cdnurl, bookid, progress):
	with tempfile.TemporaryFile() as tf:
		progress(4, "Downloading zip")
		downloadzip(cdnurl, tf, progress, 91, 4)
		zipfile = ZipFile(tf)

		progress(95, "Stitching pages")
		pdf = fitz.open()
		pages = sorted([i for i in zipfile.namelist() if i.startswith("img/") and not i.endswith("/")])
		for i in pages:
			img = fitz.open(stream=zipfile.read(i), filetype="jpeg")
			rect = img[0].rect
			pdfbytes = img.convert_to_pdf()
			img.close()
			imgpdf = fitz.open("pdf", pdfbytes)
			page = pdf.new_page(width=rect.width, height=rect.height)
			page.show_pdf_page(rect, imgpdf, 0) 

		progress(98, "Applying toc")
		toc = []
		contentxml = zipfile.open("info/content.xml").read()
		contentxml = decryptfile(contentxml, bookid)
		content = et.fromstring(contentxml)
		tocroot = content.find("TOC")
		if tocroot is not None:
			for i in tocroot.findall("item"):
				title = i.find("Title").text
				subtitle = i.find("SubTitle").text
				page = int(i.find("Page").text)
				if subtitle: 
					toc.append([1, title + " - " + subtitle, page])
				else:
					toc.append([1, title, page])
			pdf.set_toc(toc)
	return pdf
