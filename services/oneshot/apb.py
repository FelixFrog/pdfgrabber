import requests
import re
import time
import fitz

urlmatch = r'^[A-Z]{4}\d{8}$'

def downloadbook(code, progress):
    base_url = "https://updatebook.elionline.com/catalogo/index.php/CatalogUsers"

    def _insegnamento_info(token):
        response = requests.get(f'{base_url}/ProfiloStudente/', params={'userToken': token}).json()
        return response["materie_insegnamento"], response["tipo_scuola"]

    def _get_book_code(server, bundle):
        response = requests.get(f'{server}/0e7a5491c5e9c8e53df81a19b9061290/{bundle}/splash.xml', params={'d': int(time.time() * 1000)})
        return re.findall(r"codice=\"(\d+)\"", response.text)[0]

    def generate_page_labels(data):
        page_labels = []
        current_chapter = ""
        current_chapter_start = 0
        for chapter, pages in data:
            current_chapter = chapter
            for page_url, page_label, page_index in pages:
                if page_label.isdigit():
                    if current_chapter != chapter:
                        page_labels.append({
                            'startpage': current_chapter_start,
                            'prefix': current_chapter,
                            'style': 'D',
                            'firstpagenum': 1
                        })
                        current_chapter = chapter
                        current_chapter_start = page_index
                else:
                    page_labels.append({'startpage': page_index, 'prefix': f'{page_label}-', 'style': '', 'firstpagenum': 1})

        # Add the last chapter
        page_labels.append({
            'startpage': current_chapter_start,
            'prefix': current_chapter,
            'style': 'D',
            'firstpagenum': 1
        })
        return page_labels

    def book_content(server, bundle, book_code):
        response = requests.get(f'{server}/0e7a5491c5e9c8e53df81a19b9061290/{bundle}/book_{book_code}/xml/progressive_data.json').json()
        capitoli, global_page_index = [], 0
        for capitolo in response["capitoli"]:
            nome = capitolo["nome"]
            pagine = [(f'{server}/0e7a5491c5e9c8e53df81a19b9061290/{bundle}{p["risorse"][0][0].replace("swf", "png")}', p["nome"], i + global_page_index) for i, p in enumerate(capitolo["pagine"]) if p["risorse"][0][0].endswith("swf")]
            capitoli.append((nome, pagine))
            global_page_index += len(pagine)
        return capitoli

    token = requests.get(f'{base_url}/LoginStudente/', params={'username': code}).json()["token"]
    materie, scuola = _insegnamento_info(token)
    bundle_response = requests.get(f'{base_url}/SchedeStudente/', params={'userToken': token, 'tipo_scuola': scuola, 'materie_insegnamento': materie}).json()[0]
    book_code = _get_book_code(bundle_response["server"].removesuffix("/"), bundle_response["bundle"].split(".")[2])
    book_data = book_content(bundle_response["server"].removesuffix("/"), bundle_response["bundle"].split(".")[2], book_code)
    page_labels = generate_page_labels(book_data)
    chapters = [(1, chapter[0], chapter[1][0][2]) for chapter in book_data]

    pdf = fitz.open()
    for chidx, chapter in enumerate(book_data):
        chapter_title, pages = chapter
        for i, page_info in enumerate(pages):
            progress(i * 100/len(pages), f"Downloading unit {chidx+1}/{len(book_data)}")
            url, label, index = page_info
            response = requests.get(url)
            if response.status_code == 200:
                img = fitz.open("png", response.content)
                pdfbytes = img.convert_to_pdf()
                imgpdf = fitz.open("pdf", pdfbytes)
                pdf.insert_pdf(imgpdf)

    pdf.set_toc(chapters)
    pdf.set_page_labels(page_labels)

    return pdf, book_code, bundle_response["titolo"]
