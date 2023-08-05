import requests
import fitz
import re

service = "gnt"
urlmatch = r"https?://mydbook\.giuntitvp\.it/app/(?:(collections)/(\w+)|(books)/(\w+)/pdfParts)(?:/|\?[\w=&]+)?"

def downloadbook(url, progress):
	pdf = fitz.Document()
	toc = []
	labels = []

	s = requests.Session()
	s.post("https://mydbook.giuntitvp.it/login", params={"type": "normal"}, json={"ut": "public@mydbook.giuntitvp.it", "pw": "public"})
	books = s.get("https://mydbook.giuntitvp.it/books").json()

	tree = {i["codice"]: [i["children"], [j["bookcode"] for j in i["volumes"] if j["attivita"] == "pdf"]] for i in books["collections"]}
	volumetree = {i["bookcode"]: i["attivita"]["pdf"]["title"] for i in books["volumes"] if "pdf" in i["attivita"]}

	def resolvepack(packid):
		volumes = []
		if e := tree.get(packid):
			volumes.extend(e[1])
			for i in e[0]:
				volumes.extend(resolvepack(i))
		return volumes

	inputmatch = re.fullmatch(urlmatch, url)
	if inputmatch.group(1) == "collections":
		volumes = resolvepack(inputmatch.group(2))
		print("Books available:")
		for i in volumes:
			print(" - " + i + ": " + volumetree[i])
		selected = input("Choose a book: ")
		while selected not in volumes:
			selected = input("Wrong selection, try again: ")
		bookid = selected
	elif inputmatch.group(3) == "books":
		bookid = inputmatch.group(4)

	title = volumetree[bookid]
	
	pages = s.get(f"https://mydbook.giuntitvp.it/books/{bookid}/pages").json()
	numpages = len(pages["book"])
	for i, page in enumerate(pages["book"]):
		if not page["licenzapdf"]["preview"]:
			continue
		progress(i * 100/numpages, f"Downloading page {i + 1}/{numpages}")
		pagejpg = s.get(f'https://gi.shb-cdn.com/cdn/books/{bookid}/pdf/pages/{page["id"]}').content
		img = fitz.open(stream=pagejpg, filetype="jpeg")
		pdfbytes = img.convert_to_pdf()
		pdf.insert_pdf(fitz.open(stream=pdfbytes, filetype="pdf"))

	if len(pdf) <= 0:
		print("Unable to view this publicly. Aborting...")
		exit()

	'''	
	progress(98, "Applying toc/labels")
	if labels:
		pdf.set_page_labels(lib.generatelabelsrule(labels))
	pdf.set_toc(toc)
	'''
	return pdf, bookid, title