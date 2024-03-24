import utils
import version
import sys
import time
import os
import shutil
import subprocess
import requests
import main as lase
import re
import time
import ingmain
import tkinter as tk
from rich.console import Console
from rich.table import Table
from rich.rule import Rule
from rich.prompt import Prompt
from rich.prompt import Confirm
from rich.progress import Progress
import config

console = Console()
userid = False
version = version.version

console.clear()

config = config.getconfig()

banner = r"""
    ____  ____  ______                 __    __
   / __ \/ __ \/ ____/___ __________ _/ /_  / /_  ___  _____
  / /_/ / / / / /_  / __ `/ ___/ __ `/ __ \/ __ \/ _ \/ ___/
 / ____/ /_/ / __/ / /_/ / /  / /_/ / /_/ / /_/ /  __/ /
/_/   /_____/_/    \__, /_/   \__,_/_.___/_.___/\___/_/
                  /____/
"""

def create_input_window(labels, title):
    def on_ok_click():
        input_values.append(entry1.get())
        input_values.append(entry2.get())
        message_label.config(text="Close this window to submit this to PDFGrabber.")
        ok_button.config(state=tk.DISABLED)


    window = tk.Tk()
    window.title(title)

    input_values = []
    label1_text = labels[0] if len(labels) > 0 else "Label 1:"
    label2_text = labels[1] if len(labels) > 1 else "Label 2:"

    label1 = tk.Label(window, text=label1_text)
    label1.pack(pady=5)

    entry1 = tk.Entry(window)
    entry1.pack(pady=5)

    label2 = tk.Label(window, text=label2_text)
    label2.pack(pady=5)

    entry2 = tk.Entry(window, show="*")
    entry2.pack(pady=5)

    ok_button = tk.Button(window, text="OK", command=on_ok_click)
    ok_button.pack(pady=5)

    message_label = tk.Label(window, text="")
    message_label.pack(pady=5)

    window.mainloop()

    return input_values

def center(var, space=None):
	return '\n'.join(' ' * int(space or (os.get_terminal_size().columns - len(var.splitlines()[len(var.splitlines()) // 2])) / 2) + line for line in var.splitlines())

def login():
	global userid
	username, password = "", ""
	first = True
	checkpassword = config.getboolean("pdfgrabber", "AskPassword", fallback=False)
	while not (userid := utils.new_login(username, password, checkpassword)):
		if not first:
			console.print("Login invalido!", style="red")
		first = False
		if checkpassword:
			username = Prompt.ask("Username per [b]pdfgrabber[/b]")
			password = Prompt.ask("Password di [b]pdfgrabber[/b]", password=True)
		else:
			username = Prompt.ask("Username di [b]pdfgrabber[/b]", choices=utils.getusers())
	console.print("Login effettuato!", style="green")

def selectservice(services):
	console.clear()

	table = Table(title="Servizi disponibili")
	table.add_column("Code", style="cyan")
	table.add_column("Name", style="green")

	for code, name in services.items():
		table.add_row(code, name)

	console.print(table)

	chosenone = Prompt.ask("Seleziona un servizio", choices=services.keys())
	
	return chosenone

def managetokens():
	if not userid:
		login()
	table = Table(title="Tokens")
	table.add_column("Servizio", style="cyan")
	table.add_column("Token", style="green")

	for service in utils.services:
		token = utils.gettoken(userid, service)
		table.add_row(service, token[:20] + "..." if len(token or "") > 23 else "")

	console.clear()
	console.print(table)

	servicenow = Prompt.ask("Seleziona un servizio di cui eliminare il token", choices=utils.services.keys())
	utils.deletetoken(servicenow, userid)
	console.print(f"Il token per [bold]{servicenow}[/bold] è stato eliminato!")

def downloadbook():
	global userid
	if not userid:
		if not len(utils.getusers()) == 0:
			login()
		else:
			console.print('[b]Nessun utente disponibile![/b]')
			return

	console.clear()

	service = selectservice(utils.services)
	token = utils.gettoken(userid, service)
	servicename = utils.services[service]
	
	if token:
		with console.status("[bold green]Controllo token...") as status:
			check = utils.checktoken(service, token)
			if not check:
				status.update("[bold green]Aggiorno token...")
				refresh = utils.refreshtoken(service, token)
				if not refresh:
					token = ""
				else:
					token = refresh

	if not token:
		answer = Confirm.ask(f"Hai un token per [b]{servicename}[/b]?", default=False)

		if answer:
			token = Prompt.ask("Incolla qui il tuo token")
		else:
			userpassbox = create_input_window([f"Username per {servicename}", f"Password per {servicename} "], "Login")

			while len(userpassbox) == 0:
				userpassbox = create_input_window([f"Username per {servicename}", f"Password per {servicename}"], "Login")

			username = userpassbox[0]
			password = userpassbox[1]
			token = utils.login(service, username, password)
			if token:
				console.print(f"Login effettuato, il tuo token è  [bold green]{token}[/bold green]")
			else:
				console.print(f"Errore: impossibile autenticarsi a [b]{servicename}[/b]", style="red")
				return

		with console.status("[bold green]Controllo token...") as status:
			check = utils.checktoken(service, token)
			if not check:
				console.print(f"[b]{servicename}[/b] ha restituito un codice non interpretabile! Scrivi un issue su GitHub!", style="red")
				return
			else:
				utils.addtoken(userid, service, token)

	with console.status("[bold green]Scarico library...") as status:
		books = utils.library(service, token)

	if not books:
		console.print("Non hai libri (poveretto)!", style="bold red")
		return

	table = Table(title=f"Libri disponibili sul tuo account {servicename}")
	table.add_column("Id", style="cyan")
	table.add_column("Id interno", style="magenta")
	table.add_column("Titolo", style="green")

	id2bookid = []
	booktitles = []
	downloadcovers = config.getboolean(service, "Cover", fallback=False)
	for (i, (bid, book)) in enumerate(books.items()):
		if downloadcovers:
			coverpath = utils.cover(service, token, bid, book)
		table.add_row(str(i), bid, book['title'])
		booktitles.append(book['title'])
		id2bookid.append(bid)

	console.clear()
	console.print(table)

	choices = Prompt.ask("Seleziona un libro o una lista di libri seprati da una virgola (o un trattino per indicare una parte della lista compresa tra 2 numeri).").split(",")
	
	def checknumber(n):
		if n.isdigit():
			return int(n) < len(id2bookid) and int(n) >= 0
		if n.count("-") == 1:
			if all(map(checknumber, n.split("-"))):
				return n.split("-")[0] <= n.split("-")[1]
			else:
				return False
		else:
			return False

	while not all(map(checknumber, choices)):
		choices = Prompt.ask("Scelta invalida. Riprova.").split(",")


	console.clear()
	finalchoices = []
	for i in choices:
		if "-" in i:
			finalchoices.extend(list(range(int(i.split("-")[0]), int(i.split("-")[1]) + 1)))
		else:
			finalchoices.append(int(i))

	for i in finalchoices:
		bookid = id2bookid[i]
		with Progress() as progress:
			maintask = progress.add_task("Starting...", total=100)
			def progressfun(update, status=""):
				if status:
					progress.update(maintask, description=status, completed=update)
				else:
					progress.update(maintask, completed=update)

			pdfpath = utils.downloadbook(service, token, bookid, books[bookid], progressfun, booktitles[i])
			progress.update(maintask, description="Done", completed=100)

		console.clear()
		console.print(f"[bold green]Libro scaricato![/bold green] Adesso si trova in {pdfpath}")


def updates():
	# replace this url when done
	ur = requests.get("https://raw.githubusercontent.com/ErricoV1/pdfgrabber/zanichellitakedown/version.py")
	urt = ur.text
	latestversion = urt.split('version = "')[1].split('"')[0]

	# THIS is the killswitch.
	# The author can use this lever to interrupt usage of the tool.
	# Removing this means that you can be held liable for damages to boo authors.
	if latestversion == "KILL":
		console.print(center("Il servizio non è attualmente disponibile."), style="white bold")
		sys.exit(20)

	if latestversion != version:
		console.print(center('Questa versione è obsoleta!'), style="yellow bold")
		console.print(center('' + version + ' -> ' + latestversion), style="yellow bold")
		updated = False
	else:
		updated = True
	return updated

def downloadoneshot():
	console.clear()
	if config.getboolean("pdfgrabber", "OneshotWarning", fallback=True):
		answer = Confirm.ask("[bold red]I libri oneshot sono di peggior qualità e di solito contengono soltanto foto o testo non selezionabile. Vuoi continuare?[/bold red]", default=False)
		if not answer:
			return
	service = selectservice(utils.oneshots)
	servicename = utils.oneshots[service]
	urlmatch = utils.geturlmatch(service)

	url = ""
	first = True
	while not re.fullmatch(urlmatch, url):
		if not first:
			console.print(f"URL invalido per {servicename}!", style="red")
		url = Prompt.ask(f"[b]{servicename}[/b] url")

	with Progress() as progress:
		maintask = progress.add_task("Iniziando...", total=100)
		def progressfun(update, status=""):
			if status:
				progress.update(maintask, description=status, completed=update)
			else:
				progress.update(maintask, completed=update)

		pdfpath = utils.downloadoneshot(service, url, progressfun)
		progress.update(maintask, description="Fatto", completed=100)

	console.print(f"[bold green]Fatto![/bold green] Il tuo libro si trova in {pdfpath}")

def register():
	username = Prompt.ask("Username")
	password = Prompt.ask("Password", password=True)
	repeatpassword = Prompt.ask("Riscrivi la password", password=True)
	if (password != repeatpassword):
		console.print("Le password non sono uguali!", style="bold red")
		exit()
	utils.register(username, password)
	console.print(f"Ho registrato {username}, ora puoi scaricare libri!", style="bold green")

def logout():
	global userid
	userid = False
	console.print("Uscito!", style="bold magenta")

def books():
	available = utils.listbooks()
	table = Table(title="Libri")
	table.add_column("Servizio", style="cyan")
	table.add_column("Titolo", style="green")
	table.add_column("Pagine", style="magenta")
	table.add_column("Posizione", style="blue")

	for i in available:
		table.add_row(i["service"], i["title"], str(i["pages"]), i["path"])

	console.print(table)

def main():
	console.clear()
	if not (sys.version_info.major >= 3 and sys.version_info.minor >= 10):
		console.print("Ti serve Python 3.1.0 o superiore!!", style="bold red")
		exit()
	showbanner = config.getboolean("pdfgrabber", "ShowBanner", fallback=True)
	if showbanner:
		console.print(center(banner), style="green bold", no_wrap=True, highlight=False)
		console.print(Rule("versione " + version))
		console.print(center("Attenzione! Leggi il disclaimer prima di usare PDFGrabber!"), style="red bold italic")
	else:
		console.print(Rule("pdfgrabber versione " + version))

	isUpdated = updates()

	if not isUpdated:
		sys.exit(0)
	
	while True:
		action = Prompt.ask("[magenta]Cosa vuoi fare[/magenta] ((r)egistrare un nuovo utente, (s)carica qualcosa dalle tue librerie, scarica da un servizio (o)neshot, effettua il (l)ogout, organizza i (t)okens, (v)edi tutti i tuoi libri, (e)sci, seleziona una (li)ngua", default="d")
		match action:
			case "v":
				books()
			case "r":
				register()
			case "s":
				downloadbook()
			case "o":
				downloadoneshot()
			case "li":
				console.print("[b]Apro il selettore di lingue...[/b]")
				time.sleep(1)
				lase.main()
				sys.exit(0)
			case "l":
				logout()
			case "t":
				managetokens()
			case "e":
				console.print("Ciao ciao!", style="bold green")
				exit()
			case _:
				console.print("L'azione " + '"' + action + '" non esiste!', style="bold red")
		console.print(Rule())

if __name__ == '__main__':
	try:
		main()
	except KeyboardInterrupt:
		console.print("\nCiao ciao!", style="bold green")
		try:
			sys.exit(0)
		except SystemExit:
			os._exit(0)
