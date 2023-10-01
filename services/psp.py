import services.prs as prs

service = "psp"

def login(username, password):
	return prs.login(username, password, prs.pearson_plus_clientid)

def checktoken(token):
	return prs.checktoken(token)

def refreshtoken(token):
	return prs.refreshtoken(token, prs.pearson_plus_clientid)

def cover(token, bookid, data):
	return prs.cover(token, bookid, data)

def library(token):
	return prs.library(token)

def downloadbook(token, bookid, data, progress):
	return prs.downloadbook(token, bookid, data, progress)