import requests
from Crypto.Cipher import DES3
from Crypto.Util.Padding import unpad
from io import BytesIO
import zipfile
import json
from base64 import b64decode, b64encode
import umsgpack
import fitz

service = "mcm"

iv = bytes.fromhex("d2c32e0000000000")
headerxorkey = bytes.fromhex("7b58e6462235e303")

macmillan_baseurl = "https://mee2.macmillan.education"

def getlogindata(username, password, baseurl):
	r = requests.get(baseurl + "/LMS/login.php", params={"email": username, "contrasena": password})
	return r.json()

def getbaseres(token, baseurl, raw=False):
	r = requests.get(baseurl + "/LMS/downloaderPlus.php", params={"IDSESSIONDIRECT": token, "op": "getdiff", "last_update": 0, "synchromode": 1})
	if raw:
		return r.text
	else:
		return r.json()

def getbookzips(token, bookid, baseurl):
	r = requests.get(baseurl + "/LMS/downloaderPlus.php", params={"IDSESSIONDIRECT": token, "op": "getdiff", "last_update": 0, "elemid": bookid, "elem": "course", "synchromode": 2, "device": "androidapp"})
	return r.json()

def downloadzip(url, progress=False, total=0, done=0):
	showprogress = bool(progress)
	r = requests.get(url, stream=showprogress)
	if showprogress:
		length = int(r.headers.get("content-length", 1))
		file = b""
		for data in r.iter_content(chunk_size=102400):
			file += data
			progress(round(done + len(file) / length * total))
		return zipfile.ZipFile(BytesIO(file), "r")
	else:
		return zipfile.ZipFile(BytesIO(r.content), "r")

def getcover(path, baseurl):
	r = requests.get(baseurl + path)
	return r.content

def cover(token, bookid, data, baseurl=macmillan_baseurl):
	return getcover(data["cover"], baseurl)

def checktoken(token, baseurl=macmillan_baseurl):
	baseres = getbaseres(token, baseurl, True)
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

def library(token, baseurl=macmillan_baseurl):
	baseres = getbaseres(token, baseurl)

	url = next(i["url"] for i in baseres["zips"] if "tmp" in i["url"])
	ids = [i["id"] for i in baseres["elements"]["courses"]]

	userzip = downloadzip(url)

	books = dict()
	for cid in ids:
		coursejson = json.load(userzip.open("coursePlayer/curso_json_idcurso_" + cid + ".htm"))
		books[str(cid)] = {"title": coursejson["title"], "toc": b64encode(umsgpack.packb(coursejson["units"])).decode(), "cover": coursejson["image"]}
	
	return books

def downloadbook(token, bookid, data, progress, baseurl=macmillan_baseurl):
	progress(0, "Getting book zips")
	bookzips = getbookzips(token, bookid, baseurl)

	units = umsgpack.unpackb(b64decode(data["toc"]))

	files = dict()
	todownload = [i for i in bookzips["zips"] if "common" not in i["url"]]
	width = (92 - 5) / len(todownload)
	for i, file in enumerate(todownload):
		zipstart = 5 + i * width
		progress(zipstart, f"Downloading zip {i + 1}/{len(todownload)}")
		czip = downloadzip(file["url"], progress, width, zipstart)
		if file["key"]:
			for i in czip.namelist():
				if not i.endswith("/"):
					files[i.rpartition("/")[2]] = decryptfile(czip.read(i), file["key"])

	pdf = fitz.Document()
	toc = []
	pcount = 1

	progress(92, "Appending units")
	for unit in units:
		toc.append([1, unit["title"], pcount])
		for subunit in unit["subunits"]:
			sujson = json.loads(files["librodigital_json_abs_1_idclase_" + subunit["id"] + "_idcurso_" + bookid + "_type_json_xdevice_ipadapp.htm"])
			filename = sujson["pdfUrlOffline"].rpartition("/")[2]
			supdf = fitz.Document(stream=files[filename], filetype="pdf")
			pdf.insert_pdf(supdf)
			toc.append([2, sujson["title"], pcount])
			pcount += int(sujson["numPages"])

	progress(98, "Applying toc")
	pdf.set_toc(toc)
	return pdf