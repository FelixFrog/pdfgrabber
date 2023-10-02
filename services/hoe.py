import services.bsm as bsm

service = "hoe"

hoepliacademy_baseurl = "https://www.hoepliacademy.it"

def login(username, password):
	return bsm.login(username, password, hoepliacademy_baseurl)

def checktoken(token):
	return bsm.checktoken(token, hoepliacademy_baseurl)

def cover(token, bookid, data):
	return bsm.cover(token, bookid, data)

def library(token):
	return bsm.library(token, hoepliacademy_baseurl, service)

def downloadbook(token, bookid, data, prorgess):
	return bsm.downloadbook(token, bookid, data, prorgess, hoepliacademy_baseurl)