from Crypto.Hash import SHA256
from Crypto.Random import get_random_bytes
from base64 import urlsafe_b64encode
import requests
import uuid
import lxml.html
import urllib.parse
import fitz
from zipfile import ZipFile
from pathlib import Path
from io import BytesIO
from playwright.sync_api import sync_playwright
from tempfile import TemporaryDirectory
import lib
import json
import re
import config

service = "cng"

appid = "43a266a6-ff71-473d-896a-7b33b60f901c"

configfile = config.getconfig()

def getloginconfig():
	r = requests.get(f"https://hapicen.com/v1/reader/{appid}/config")
	return r.json()

def getopenidconfig(openidurl):
	r = requests.get(f"{openidurl}/.well-known/openid-configuration")
	return r.json()

def getloginpage(authorizeurl, logincontext, state, code_challenge, code_challenge_method, idp, clientid, redirecturi):
	params = {"client_id": clientid, "response_type": "code", "prompt": "login", "state": state, "scope": "openid offline_access puma-entitlements-read-self", "code_challenge": code_challenge, "code_challenge_method": code_challenge_method}
	'''
	paramsenc = urllib.parse.urlencode(params | {"redirect_uri": redirecturi, "idp": idp})
	redirect = f"{authorizeurl}?{paramsenc}"
	r = requests.get(logincontext, params=params | {"redirect_uri": redirect})
	'''
	r = requests.get(authorizeurl, params=params | {"redirect_uri": redirecturi, "idp": idp})
	return r.text

def gettoken(username, password):
	r = requests.post("https://auth.cengage.com/api/v1/authn", json={"password": password, "username": username, "options": {"warnBeforePasswordExpired": True, "multiOptionalFactorEnroll": False}})
	return r.json()

def getcode(oktakey, sessiontoken):
	params = urllib.parse.urlencode({"okta_key": oktakey})
	redirect = f"https://auth.cengage.com/oauth2/v1/authorize/redirect?{params}"
	s = requests.Session()
	r = s.get("https://auth.cengage.com/login/sessionCookieRedirect", params={"checkAccountSetupComplete": False, "token": sessiontoken, "redirectUrl": redirect}, allow_redirects=False)
	r2 = s.get(r.headers["location"], allow_redirects=False)
	return r2.headers["location"]

def getlibrary(token):
	r = requests.get("https://hapicen.com/v2/reader/books/store", params={"app_id": appid}, headers={"Authorization": f"Bearer {token}"})
	return r.json()

def getaccesstoken(code, code_verifier):
	r = requests.post("https://dbn-prod-cen-gateway.cenplatform.com/graphql", headers={"x-gt-client-name": "android", "x-gt-client-version": "353"}, json={"operationName": "connectWithOidc", "variables": {"distributionChannelId": appid, "redirectUri": "msauth.com.cengage.mobile://auth/", "callbackParams": {"code": code, "scope": "openid offline_access puma-entitlements-read-self"}, "callbackChecks": {"code_verifier": code_verifier}}, "query": "mutation connectWithOidc($clientMutationId: String, $distributionChannelId: String!, $redirectUri: String!, $callbackParams: OidcCallbackParams!, $callbackChecks: OidcCallbackChecks!) { connectWithOidc(input: {clientMutationId: $clientMutationId, distributionChannelId: $distributionChannelId, redirectUri: $redirectUri, callbackParams: $callbackParams, callbackChecks: $callbackChecks}) { __typename clientMutationId accessToken refreshToken userErrors { __typename code message path } } }"})
	return r.json()

def getrefreshtoken(refreshtoken):
	mutationid = generate_uuid()
	r = requests.post("https://dbn-prod-cen-gateway.cenplatform.com/graphql", headers={"x-gt-client-name": "android", "x-gt-client-version": "353"}, json={"operationName": "refreshToken", "variables": {"input": {"clientMutationId": f"{appid}_{mutationid}","refreshToken": refreshtoken}}, "query": "mutation refreshToken($input: RefreshTokenInput!) { refreshToken(input: $input) { __typename accessToken clientMutationId refreshToken } }"})
	return r.json()

def getme(accesstoken):
	r = requests.post("https://dbn-prod-cen-gateway.cenplatform.com/graphql", headers={"x-gt-client-name": "android", "x-gt-client-version": "353", "Authorization": f"Bearer {accesstoken}"}, json={"operationName": "me", "variables": {}, "query": "query me { me { __typename id avatar createdAt email firstName isActivated lastName updatedAt watermark workspaceId distributionChannels { __typename conditions { __typename id isRequired link type version } id hasUserSignedRequiredCondition } } }"})
	return r.json()

def getzipurl(token, contentid, version, btype):
	r = requests.get(f"https://hapicen.com/v1/reader/store/link/{contentid}/{version}/{btype}", headers={"Authorization": f"Bearer {token}"})
	return r.text

def downloadfile(url, progress, total, done):
	r = requests.get(url, stream=True)
	length = int(r.headers.get("content-length", 1))
	file = b""
	for data in r.iter_content(chunk_size=102400):
		file += data
		progress(round(done + len(file) / length * total))
	return file

def generate_code_verifier():
	code_verifier = urlsafe_b64encode(get_random_bytes(64)).strip(b"=")
	h = SHA256.new()
	h.update(code_verifier)
	code_challenge = urlsafe_b64encode(h.digest()).strip(b"=")
	code_challenge_method = "S256"
	return code_verifier.decode(), code_challenge.decode(), code_challenge_method

def generate_uuid():
	return str(uuid.uuid4())

def login(username, password):
	loginconfig = getloginconfig()
	for i in loginconfig["ssos"]:
		if i["id"] == "CengageOkta":
			issuerurl = i["issuerUrl"]
			clientid = i["clientId"]
			redirecturi = i["redirectUri"]
			logincontext = i["thirdparty"]["loginContextEndpoint"]
			idp = i["thirdparty"]["idp"]
			break
	openidconfig = getopenidconfig(issuerurl)
	authorizeurl = openidconfig["authorization_endpoint"]

	state = generate_uuid()
	code_verifier, code_challenge, code_challenge_method = generate_code_verifier()

	loginpage = lxml.html.document_fromstring(getloginpage(authorizeurl, logincontext, state, code_challenge, code_challenge_method, idp, clientid, redirecturi))
	form = loginpage.get_element_by_id("appForm")
	oktakey = ""
	for i in form:
		if i.tag == "input" and i.get("type") == "hidden":
			#params[i.get("name")] = i.get("value")
			# we could send the request but we just need the okta_key
			if i.get("name") == "RelayState":
				relaystatevalue = urllib.parse.unquote(i.get("value"))
				oktakey = urllib.parse.parse_qs(relaystatevalue.split("?")[1])["okta_key"][0]
	if not oktakey:
		print("Cannot get the okta_key! Error!")
		return

	token = gettoken(username, password)
	if "errorSummary" in token:
		print(f"Can't log in: {token['errorSummary']}")
		return

	sessiontoken = token["sessionToken"]
	appuri = getcode(oktakey, sessiontoken)
	code = urllib.parse.parse_qs(appuri.split("?")[1])["code"][0]

	finaltoken = getaccesstoken(code, code_verifier)
	return finaltoken["data"]["connectWithOidc"]["accessToken"] + "|" + finaltoken["data"]["connectWithOidc"]["refreshToken"]

def checktoken(token):
	accesstoken, refreshtoken = token.split("|")
	me = getme(accesstoken)
	return "errors" not in me

def refreshtoken(token):
	accesstoken, refreshtoken = token.split("|")
	newtokens = getrefreshtoken(refreshtoken)
	newaccess = newtokens["data"]["refreshToken"]["accessToken"]
	newrefresh = newtokens["data"]["refreshToken"]["refreshToken"]
	if newaccess and newrefresh:
		return newaccess + "|" + newrefresh

def cover(token, bookid, data):
	r = requests.get(data["url"])
	return r.content

def library(token):
	accesstoken, refreshtoken = token.split("|")
	library = getlibrary(accesstoken)
	books = {}
	if "error" in library:
		print(library)
		return books

	for book in library[0]["books"]:
		metas = {}
		for i in book["metas"]["value"] + book["project_metas"]["value"]:
			metas[i["name"]] = i["value"]
		# Maybe in the future we should check wether books with "available", "compatible", "bought" == False or "licenseEndDate" > now or "type" != "book" are downloadable
		books[book["id"]] = {"title": metas["Title"], "isbn": book["isbn"], "cover": book["cover"], "type": book["book_type"], "contentid": book["book_content_id"], "version": book["version"]}

	return books

def downloadhtml5(token, data, progress):
	pdf = fitz.Document()
	toc, labels = [], []

	progress(2, "Getting zip url")
	zipurl = getzipurl(token, data["contentid"], data["version"], data["type"])

	progress(4, "Downloading zip")
	bookzip = ZipFile(BytesIO(downloadfile(zipurl, progress, 40, 4)))

	incr = 0
	def linearize(p, level, r):
		s = r
		pages = []
		toc = []
		for i in p["content"]:
			if i["modelName"] == "page" and i["isPage"] == "true" and (i["display"] == "true" or configfile.getboolean(service, "AddHiddenPages", fallback=True)):
				pages.append(i)
				#if i["title"] != i["logicalPageNumber"]:
				if "title" in i:
					toc.append([level, i["title"], s])
				s += 1
			elif "content" in i: # or i["modelName"] == "section-chapter"
				if "title" in i:
					toc.append([level, i["title"], s])
				toadd, toaddtoc, toadds = linearize(i, level + 1, s)
				toc.extend(toaddtoc)
				pages.extend(toadd)
				s += (toadds - s)

		return pages, toc, s

	with TemporaryDirectory(prefix="cengagehtml5.", ignore_cleanup_errors=True) as tmpdirfull:
		tmpdir = Path(tmpdirfull)

		progress(46, "Extracting zip")
		bookzip.extractall(path=tmpdir)
		del(bookzip)

		structure = json.load(open(tmpdir / "structure.json", "r", encoding="utf-8"))
		pagesizemap = {}
		papersize = configfile.get(service, "PaperSizeLiquidBooks", fallback="A4")
		istocdirty = False
		with sync_playwright() as p:
			browser = p.chromium.launch()
			bpage = browser.new_page()
			totpages, toc, totnum = linearize(structure["book"], 1, 1)
			for i, page in enumerate(totpages):
				pagefile = tmpdir / page["localPath"]
				if not pagefile.exists():
					print("Page file doens't exist, skipping...")
					continue

				if page.get("logicalPageNumber"):
					labels.append(page["title"])
				else:
					labels.append(str(len(pdf) + 1))

				pagesizemap[(i + 1)] = (len(pdf) + 1)

				progress(48 + (((i + 1) / totnum) * 50), f"Rendering page {(i + 1)}/{totnum}")
				bpage.goto(pagefile.as_uri())
				if configfile.getboolean(service, "SelectableTextHack", fallback=True):
					bpage.locator(".textLayer > span").evaluate_all("elements => elements.forEach((i) => i.style.color = '#00000001');")
				if page.get("width") and page.get("height"):
					width, height = str(float(page["width"])) + "px", str(float(page["height"])) + "px"
					pdfpagebytes = bpage.pdf(print_background=True, width=width, height=height, page_ranges="1")
				else:
					istocdirty = True
					pdfpagebytes = bpage.pdf(print_background=True, format=papersize)
				pagepdf = fitz.Document(stream=pdfpagebytes, filetype="pdf")
				pdf.insert_pdf(pagepdf)

			browser.close()

		if istocdirty:
			for i in toc:
				i[2] = pagesizemap[i[2]]

	progress(98, "Applying toc/labels")
	pdf.set_page_labels(lib.generatelabelsrule(labels))
	pdf.set_toc(lib.cleantoc(toc))
	return pdf

def downloadbook(token, bookid, data, progress):
	accesstoken, refreshtoken = token.split("|")
	match data["type"]:
		case "html5":
			pdf = downloadhtml5(accesstoken, data, progress)
		case _:
			print(f"Books of type {data['type']} are not supported yet! Contact us to add support for it!")
			exit()

	return pdf
