import importlib
import fitz
from tinydb import TinyDB, Query
from hashlib import sha256
from pathlib import Path
import os
import config

os.chdir(Path(__file__).parent)

config = config.getconfig()

db = TinyDB("db.json")
usertable = db.table("users")
tokentable = db.table("tokens")
booktable = db.table("books")

services = {"bsm": "bSmart", "ees": "easyeschool", "hbs": "Mondadori HUB Scuola", "mcm": "MEE2", "myl": "MyLim", "prs": "Pearson eText / Reader+", "psp": "Pearson+", "sbk": "Scuolabook", "znc": "Zanichelli Booktab / Kitaboo", "dbk": "Laterza diBooK", "olb": "Oxford Learner’s Bookshelf", "rfl": "Raffaello Player", "cmb": "Cambridge GO", "blk": "Blinklearning", "hoe": "HoepliAcademy+"}
oneshots = {"gnt": "mydBook Giunti TVP"}

def getservice(name, oneshot=False):
	if oneshot:
		service = importlib.import_module("services.oneshot." + name)
	else:
		service = importlib.import_module("services." + name)
	return service

def login(servicename, username, password):
	service = getservice(servicename)
	token = service.login(username, password)
	return token

def checkpath(path):
	os.makedirs(path.parent, exist_ok=True)

def downloadbook(servicename, token, bookid, data, progress):
	service = getservice(servicename)
	pdfpath = Path("files") / servicename / (f"{bookid}.pdf")
	checkpath(pdfpath)
	
	pdf = service.downloadbook(token, bookid, data, progress)
	pdfnow = fitz.utils.get_pdf_now()

	author = config.get(servicename, "Author", fallback="none")

	metadata = {'producer': "PyMuPDF " + fitz.version[0], 'format': 'PDF 1.7', 'encryption': None, 'author': 'none', 'modDate': pdfnow, 'keywords': 'none', 'title': data["title"], 'creationDate': pdfnow, 'creator': "pdfgrabber1.0", 'subject': 'none'}
	pdf.set_metadata(metadata)
	progress(99, "Saving pdf")
	if config.getboolean(servicename, "Compress", fallback=False):
		pdf.save(pdfpath, garbage=config.getint(servicename, "Garbage", fallback=3), clean=config.getboolean(servicename, "Clean", fallback=True), linear=config.getboolean(servicename, "Linearize", fallback=True))
	else:
		pdf.save(pdfpath)

	booktable.upsert({"service": servicename, "bookid": bookid, "title": data["title"], "pages": len(pdf), "path": str(pdfpath)}, (Query().service == servicename) and (Query().bookid == bookid))
	return pdfpath

def downloadoneshot(servicename, url, progress):
	service = getservice(servicename, oneshot=True)

	result = service.downloadbook(url, progress)
	if not result:
		print("Invalid link!")
		exit()
	pdf, bookid, title = result
	pdfpath = Path("files") / servicename / (f"{bookid}.pdf")
	checkpath(pdfpath)

	pdfnow = fitz.utils.get_pdf_now()

	author = config.get(servicename, "Author", fallback="none")

	metadata = {'producer': "PyMuPDF " + fitz.version[0], 'format': 'PDF 1.7', 'encryption': None, 'author': author, 'modDate': pdfnow, 'keywords': 'none', 'title': title, 'creationDate': pdfnow, 'creator': "pdfgrabber1.0", 'subject': 'none'}
	pdf.set_metadata(metadata)
	progress(99, "Saving pdf")
	if config.getboolean(servicename, "EzSave", fallback=True):
		pdf.ez_save(pdfpath)
	else:
		if config.getboolean(servicename, "Compress", fallback=False):
			pdf.save(pdfpath, garbage=config.getint(servicename, "Garbage", fallback=3), clean=config.getboolean(servicename, "Clean", fallback=True), linear=config.getboolean(servicename, "Linearize", fallback=True))
		else:
			pdf.save(pdfpath)

	booktable.upsert({"service": servicename, "bookid": bookid, "title": title, "pages": len(pdf), "path": str(pdfpath)}, (Query().service == servicename) and (Query().bookid == bookid))
	return pdfpath

def cover(servicename, token, bookid, data):
	from os.path import isfile
	coverpath = Path("files") / servicename / (f"cover-{bookid}.png")
	#coverpath = "files/" + servicename + "/cover-" + bookid + ".png"
	checkpath(coverpath)
	if not isfile(coverpath):
		service = getservice(servicename)
		open(coverpath, "wb").write(service.cover(token, bookid, data))
	return coverpath

def library(servicename, token):
	service = getservice(servicename)
	return service.library(token)

def checktoken(servicename, token):
	service = getservice(servicename)
	return service.checktoken(token)

def refreshtoken(servicename, token):
	service = getservice(servicename)
	if hasattr(service, "refreshtoken"):
		return service.refreshtoken(token)

def new_login(username, password, checkpassword=True):
	passwordhash = sha256(password.encode()).hexdigest()
	if checkpassword:
		user = usertable.get((Query().password == passwordhash) & (Query().name == username))
	else:
		user = usertable.get((Query().name == username))
	if user:
		return user.doc_id

def getusers():
	return [i["name"] for i in usertable.all()]

def listbooks():
	return booktable.all()

def geturlmatch(servicename):
	service = getservice(servicename, oneshot=True)
	return service.urlmatch

def deletetoken(service, userid):
	tokentable.remove((Query().service == service) & (Query().owner == userid))

def gettoken(userid, service=""):
	if service:
		token = tokentable.get((Query().owner == userid) & (Query().service == service))
		if token:
			return token["value"]
	else:
		return tokentable.search(Query().owner == userid)

def register(username, password):
	passwordhash = sha256(password.encode()).hexdigest()
	return usertable.insert({"name": username, "password": passwordhash})

def delete(userid):
	usertable.remove(doc_id=userid)

def addtoken(userid, servicename, token):
	tokentable.upsert({"owner": userid, "service": servicename, "value": token}, (Query().owner == userid) & (Query().service == servicename))
