import requests
from Crypto.Cipher import DES3
from Crypto.Util.Padding import unpad
from zipfile import ZipFile
import json
from base64 import b64decode, b64encode
import fitz
import tempfile

service = "mcm"

iv = bytes.fromhex("d2c32e0000000000")
headerxorkey = bytes.fromhex("7b58e6462235e303")

macmillan_baseurl = "https://mee2.macmillan.education"

def getlogindata(username, password, baseurl):
	r = requests.get(baseurl + "/LMS/login.php", params={"email": username, "contrasena": password})
	return r.json()

def getbaseres(token, baseurl):
	r = requests.get(baseurl + "/LMS/downloaderPlus.php", params={"IDSESSIONDIRECT": token, "op": "getdiff", "last_update": 0, "synchromode": 1})
	if r.status_code == 200:
		return r.json()
	else:
		return None

def getbookzips(token, bookid, baseurl):
	r = requests.get(baseurl + "/LMS/downloaderPlus.php", params={"IDSESSIONDIRECT": token, "op": "getdiff", "last_update": 0, "elemid": bookid, "elem": "course", "synchromode": 2, "device": "androidapp"})
	return r.json()

def downloadzip(url, tmpfile, progress=False, total=0, done=0):
	showprogress = bool(progress)
	r = requests.get(url, stream=showprogress)
	length = int(r.headers.get("content-length", 1))
	for data in r.iter_content(chunk_size=102400):
		tmpfile.write(data)
		if showprogress:
			progress(round(done + tmpfile.tell() / length * total))

def getresource(path, baseurl):
	r = requests.get(baseurl + path)
	return r.content

def cover(token, bookid, data, baseurl=macmillan_baseurl):
	return getresource(data["cover"], baseurl)

def checktoken(token, baseurl=macmillan_baseurl):
	baseres = getbaseres(token, baseurl)
	return bool(baseres)

def decryptfile(file, key):
	if not key:
		return file
	else:
		cipher = DES3.new(key, DES3.MODE_CBC, iv)
		dec = cipher.decrypt(file)
		header = bytes([a ^ b for (a, b) in zip(headerxorkey, dec[:8])])
		return unpad(header + dec[8:], DES3.block_size)

def login(username, password, baseurl=macmillan_baseurl):
	logindata = getlogindata(username, password, baseurl)
	if logindata["result"] != "OK":
		print("Login failed: " + logindata["msg"])
	else:
		#import time
		#print("Expires "  + str(int(time.mktime(time.strptime(logindata["mode_expiration"], "%Y%m%d%H%M%S")))))
		return logindata["userToken"]

def identifyuserzip(token, baseres, baseurl):
	urls = [i["url"] for i in baseres["zips"] if "tmp" in i["url"]]
	tf = tempfile.TemporaryFile()
	for url in urls:
		userzip = downloadzip(url, tf)
		userzip = ZipFile(tf)
		if "coursePlayer/" in userzip.namelist():
			return userzip
		else:
			tf.close()
			tf = tempfile.TemporaryFile()

def library(token, baseurl=macmillan_baseurl):
	baseres = getbaseres(token, baseurl)

	ids = [i["id"] for i in baseres["elements"]["courses"]]

	userzip = identifyuserzip(token, baseres, baseurl)

	books = dict()
	for cid in ids:
		coursejson = json.load(userzip.open("coursePlayer/curso_json_idcurso_" + cid + ".htm"))
		books[str(cid)] = {"title": coursejson["title"], "cover": coursejson["image"], "isbn": coursejson["isbn"].replace("-", "")}
	
	return books

def downloadbook(token, bookid, data, progress, baseurl=macmillan_baseurl):
	progress(0, "Getting book zips")
	bookzips = getbookzips(token, bookid, baseurl)

	userzip = identifyuserzip(token, getbaseres(token, baseurl), baseurl)

	courseinfo = json.load(userzip.open("coursePlayer/curso_json_idcurso_" + bookid + ".htm"))

	files = dict()
	todownload = [i for i in bookzips["zips"] if "common" not in i["url"]]
	width = (92 - 5) / len(todownload)
	for i, file in enumerate(todownload):
		zipstart = 5 + i * width
		progress(zipstart, f"Downloading zip {i + 1}/{len(todownload)}")
		with tempfile.TemporaryFile() as tf:
			downloadzip(file["url"], tf, progress, width, zipstart)
			czip = ZipFile(tf)
			if file["key"]:
				for i in czip.namelist():
					if not i.endswith("/"):
						files[i.rpartition("/")[2]] = decryptfile(czip.read(i), file["key"])

	pdf = fitz.Document()
	toc = []

	progress(92, "Appending units")
	for unit in courseinfo["units"]:
		#toc.append([1, unit["title"], len(pdf) + 1])
		for subunit in unit["subunits"]:
			jsonpath = "librodigital_json_abs_1_idclase_" + subunit["id"] + "_idcurso_" + bookid + "_type_json_xdevice_ipadapp.htm"
			if not jsonpath in files or subunit["type"] != "libro":
				continue
			sujson = json.loads(files[jsonpath])
			filename = sujson["pdfUrlOffline"].rpartition("/")[2]
			if not filename.endswith(".pdf"):
				continue
			supdf = fitz.Document(stream=files[filename], filetype="pdf")
			toc.append([int(subunit["level"]), sujson["title"], len(pdf) + 1])
			pdf.insert_pdf(supdf)

	progress(98, "Applying toc")
	pdf.set_toc(toc)
	return pdf