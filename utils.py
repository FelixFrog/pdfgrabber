import importlib
import fitz
from tinydb import TinyDB, Query
from hashlib import sha256
from pathlib import Path
import os

db = TinyDB("db.json")
usertable = db.table("users")
tokentable = db.table("tokens")
booktable = db.table("books")

services = {"bsm": "bSmart", "ees": "easyeschool", "hby": "Mondadori Hub Young", "mcm": "MEE2", "myl": "MyLim", "prn": "Pearson eText / Reader+", "sbk": "Scuolabook", "znc": "Zanichelli Booktab / Kitaboo", "dbk": "Laterza diBooK", "olb": "Oxford Learner’s Bookshelf"}

def getservice(name):
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
	#pdfpath = "files/" + servicename + "/" + bookid + ".pdf"
	
	pdf = service.downloadbook(token, bookid, data, progress)
	pdfnow = fitz.utils.get_pdf_now()

	metadata = {'producer': "PyMuPDF " + fitz.version[0], 'format': 'PDF 1.7', 'encryption': None, 'author': 'none', 'modDate': pdfnow, 'keywords': 'none', 'title': data["title"], 'creationDate': pdfnow, 'creator': "pdfgrabber1.0", 'subject': 'none'}
	pdf.set_metadata(metadata)
	progress(99, "Saving pdf")
	# This saves a bit of spaces but sometimes causes the disappearence of the first page. Dunno Y
	#pdf.save(pdfpath, garbage=3, clean=True, linear=True)
	pdf.save(pdfpath)
	booktable.upsert({"service": servicename, "bookid": bookid, "title": data["title"], "pages": len(pdf), "path": str(pdfpath)}, (Query().service == servicename) and (Query().bookid == bookid))
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

def new_login(username, password):
	passwordhash = sha256(password.encode()).hexdigest()
	user = usertable.get((Query().password == passwordhash) & (Query().name == username))
	if user:
		return user.doc_id

def listbooks():
	return booktable.all()

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
	tokentable.upsert({"owner": userid, "service": servicename, "value": token}, (Query().owner == userid) and (Query().service == servicename))
