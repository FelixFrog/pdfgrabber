import requests
import fitz
from base64 import b64decode, b64encode
import time
import xml.etree.ElementTree as et

service = "ktb"
urlmatch = r"http[s]{,1}://my\.zanichelli\.it/kitaboo/[0-9a-f]{32}[/]{,1}"

clientid = b64encode("ZanichelliAdapter".encode())

def downloadbook(url, progress):
	pdf = fitz.Document()
	toc = []
	labels = []

	s = requests.Session()
	index = s.get(url, allow_redirects=False)
	location = index.headers["Location"]
	if "usertoken" not in location or "bookID" not in location:
		return

	params = {i.split("=")[0]: i.split("=")[1] for i in location.split("?")[-1].split("&")}
	tokenvalidation = s.get("https://zanichelliservices.kitaboo.eu/DistributionServices/services/api/reader/user/123/pc/validateUserToken", params={"usertoken": params["usertoken"], "t": int(time.time()), "clientID": clientid}).json()
	usertoken = tokenvalidation["userToken"]

	bookdetails = requests.get("https://zanichelliservices.kitaboo.eu/DistributionServices/services/api/reader/distribution/123/pc/book/details", params={"bookID": params["bookID"], "t": int(time.time())}, headers={"usertoken": usertoken}).json()
	# TODO: choose a better selection method
	book = bookdetails["bookList"][0]
	if book["encryption"]:
		print("Encrypted books unsupported!")
		return

	ebookid = book["book"]["ebookID"]
	auth = s.get("https://webreader.zanichelli.it/ContentServer/mvc/authenticatesp", params={"packageId": ebookid, "ut": usertoken, "ds": "y", "t": int(time.time())})
	bearer = auth.headers["Authorization"]
	s.get("https://webreader.zanichelli.it/ContentServer/mvc/getSessionForBook", params={"bookId": ebookid}, headers={"Authorization": bearer})
	info = requests.get("https://zanichelliservices.kitaboo.eu/DistributionServices/services/api/reader/distribution/123/html5/" + params["bookID"] + "/downloadBook", params={"state": "online", "t": int(time.time())}, headers={"usertoken": usertoken}).json()
	baseurl = info["responseMsg"].replace("http://", "https://")

	info = s.get(baseurl + "/META-INF/container.xml")

	ns = {"xhtml": "http://www.w3.org/1999/xhtml", "ops": "http://www.idpf.org/2007/ops", "opf": "http://www.idpf.org/2007/opf", "dc": "http://purl.org/dc/elements/1.1/"}
	contentspath = et.fromstring(info.text).find("{urn:oasis:names:tc:opendocument:xmlns:container}rootfiles").find("{urn:oasis:names:tc:opendocument:xmlns:container}rootfile").get("full-path")
	contents = et.fromstring(s.get(baseurl + "/" + contentspath).content)
	
	metadata = contents.find("opf:metadata", ns)
	title = " - ".join([metadata.find("dc:title", ns).text, metadata.find("dc:description", ns).text, metadata.find("dc:author", ns).text])

	files = {i.get("id"): i.attrib for i in contents.find("opf:manifest", ns).findall("opf:item", ns)}
	pages = sorted([attrs["href"] for file, attrs in files.items() if attrs["media-type"] == "image/svg+xml"])

	basepath = baseurl + "/" + "/".join(contentspath.split("/")[:-1]) + "/"

	for i , page in enumerate(pages):
		progress(i * 100/len(pages), f"Rendering page {i}/{len(pages)}")
		svg = fitz.open(stream=s.get(basepath + page).text.replace("data:image/jpg;base64", "data:image/jpeg;base64").encode(), filetype="svg")
		pdf.insert_pdf(fitz.open(stream=svg.convert_to_pdf()))

	'''	
	progress(98, "Applying toc/labels")
	if labels:
		pdf.set_page_labels(lib.generatelabelsrule(labels))
	pdf.set_toc(toc)
	'''
	return pdf, ebookid, title
