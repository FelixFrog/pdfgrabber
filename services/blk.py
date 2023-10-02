import services.mcm as mcm

service = "blk"

blinklearning_baseurl = "https://www.blinklearning.com"

def login(username, password):
	return mcm.login(username, password, blinklearning_baseurl)

def checktoken(token):
	return mcm.checktoken(token, blinklearning_baseurl)

def cover(token, bookid, data):
	return mcm.cover(token, bookid, data, blinklearning_baseurl)

def library(token):
	return mcm.library(token, blinklearning_baseurl)

def downloadbook(token, bookid, data, prorgess):
	return mcm.downloadbook(token, bookid, data, prorgess, blinklearning_baseurl)