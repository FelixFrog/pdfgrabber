from Crypto.Hash import SHA512
from Crypto.Random import get_random_bytes
from lxml import etree as et
import fitz
import requests
from zipfile import ZipFile
import services.olb as olb
import config

service = "orc"

secretkey = b"EEECCB78348935BA30B4BAB6F5365D06"

configfile = config.getconfig()

def getaccesskey(username, hashedpwd):
	r = requests.post("https://api.oxfordreadingclub.com/api/v2/auth/login", json={"deviceId": get_random_bytes(16).hex(), "isUnderSixteen": False, "marketingReception": False, "model": "Android", "os": "Android", "password": hashedpwd, "userId": username})
	return r.json()

def getuserinfo(token):
	r = requests.post("https://api.oxfordreadingclub.com/api/auth/userinfo", data={"accessKey": token})
	return r.json()

def getlibrary(token):
	r = requests.get("https://api.oxfordreadingclub.com/api/portal/v2/user/book/with-user-study-record", headers={"accessKey": token})
	return r.json()

def getsignedurl(fullurl, xauth, timemillis):
	r = requests.get(fullurl, headers={"X-Authorization": xauth, "X-Timestamp": timemillis})
	return r.json()

def downloadzip(url, tempfile, progress, total, done):
	r = requests.get(url, stream=True)
	length = int(r.headers.get("content-length", 1))
	tot = 0
	for data in r.iter_content(chunk_size=102400):
		tot += tempfile.write(data)
		progress(round(done + tot / length * total))

def getcover(url):
	r = requests.get(url)
	return r.content

def login(username, password):
	pwdhasher = SHA512.new()
	pwdhasher.update(password.encode())
	logindata = getaccesskey(username, pwdhasher.hexdigest().upper())
	if logindata["code"] != 200:
		print("Login failed: " + logindata["message"])
		return
	else:
		return logindata["accessKey"]

def checktoken(token):
	userinfo = getuserinfo(token)
	return userinfo["code"] == 200

def library(token):
	library = getlibrary(token)

	books = {}
	for i in library["data"]:
		if i["productInfo"]["expired"] and not configfile.getboolean(service, "AllowExpired", fallback=True):
			continue
		m = i["metaData"]
		books[m["bid"]] = {"title": m["title"], "cover": m["coverImg"], "isbn": m["isbnPrint"], "author": m["author"], "url": m["contentZipUrl"]}
	return books

def cover(token, bookid, data):
	return getcover(data["cover"])

def downloadbook(token, bookid, data, progress):
	progress(2, "Signing url")
	fullurl = "https://cms.oxfordreadingclub.jp/api/v1/signed_url?url=" + data["url"]
	xauth, timemillis = olb.computexauth(olb.truncateurl(fullurl), secretkey)
	signedurlresp = getsignedurl(fullurl, xauth, timemillis)
	signedurl = signedurlresp["results"]["signed_url"]

	return olb.downloadoxfordbook(signedurl, bookid, progress)

