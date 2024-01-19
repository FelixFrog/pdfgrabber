import services.prs as prs

service = "psp"

# pearson_plus_clientid = "cGnFEyiajGgv2EhcShCPBa7jqwSFpSG5" # probably deprecated

def login(username, password):
	return prs.login(username, password, False)

def checktoken(token):
	return prs.checktoken(token)

def refreshtoken(token):
	return prs.refreshtoken(token)

def cover(token, bookid, data):
	return prs.cover(token, bookid, data)

def library(token):
	return prs.library(token, False)

def downloadbook(token, bookid, data, progress):
	return prs.downloadbook(token, bookid, data, progress)