import utils
import sys
import os
import re
from rich.console import Console
from rich.table import Table
from rich.rule import Rule
from rich.prompt import Prompt
from rich.prompt import Confirm
from rich.progress import Progress
import config

console = Console()
userid = False

config = config.getconfig()

banner = """
    ____  ____  ______                 __    __
   / __ \/ __ \/ ____/___ __________ _/ /_  / /_  ___  _____
  / /_/ / / / / /_  / __ `/ ___/ __ `/ __ \/ __ \/ _ \/ ___/
 / ____/ /_/ / __/ / /_/ / /  / /_/ / /_/ / /_/ /  __/ /
/_/   /_____/_/    \__, /_/   \__,_/_.___/_.___/\___/_/
                  /____/
"""

def center(var:str, space:int=None):
	'''center elements (text) in the terminal'''
	return '\n'.join(' ' * int(space or (os.get_terminal_size().columns - len(var.splitlines()[len(var.splitlines()) // 2])) / 2) + line for line in var.splitlines())

def login():
	global userid
	username, password = "", ""
	first = True
	checkpassword = config.getboolean("pdfgrabber", "AskPassword", fallback=False)
	while not (userid := utils.new_login(username, password, checkpassword)):
		if not first:
			console.print("Invalid login!", style="red")
		first = False
		if checkpassword:
			username = Prompt.ask("[b]pdfgrabber[/b] username")
			password = Prompt.ask("[b]pdfgrabber[/b] password", password=True)
		else:
			username = Prompt.ask("[b]pdfgrabber[/b] username", choices=utils.getusers())
	console.print("Logged in!", style="green")

def selectservice(services):
	table = Table(title="Available services")
	table.add_column("Code", style="cyan")
	table.add_column("Name", style="green")

	for code, name in services.items():
		table.add_row(code, name)

	console.print(table)

	return Prompt.ask("Choose a service", choices=services.keys())

def managetokens():
	if not userid:
		login()
	table = Table(title="Tokens")
	table.add_column("Service", style="cyan")
	table.add_column("Token", style="green")

	for service in utils.services:
		token = utils.gettoken(userid, service)
		table.add_row(service, token[:20] + "..." if len(token or "") > 23 else "")

	console.print(table)

	servicenow = Prompt.ask("Choose a service to delete the token from", choices=utils.services.keys())
	utils.deletetoken(servicenow, userid)
	console.print(f"Token for [bold]{servicenow}[/bold] deleted!")

def downloadbook():
	global userid
	if not userid:
		login()

	service = selectservice(utils.services)
	token = utils.gettoken(userid, service)
	servicename = utils.services[service]
	
	if token:
		with console.status("[bold green]Checking token...") as status:
			check = utils.checktoken(service, token)
			if not check:
				status.update("[bold green]Refreshing token...")
				refresh = utils.refreshtoken(service, token)
				if not refresh:
					token = ""
				else:
					token = refresh

	if not token:
		answer = Confirm.ask(f"Do you have a token for [b]{servicename}[/b]?", default=False)

		if answer:
			token = Prompt.ask("Paste here your token")
		else:
			username = Prompt.ask(f"[b]{servicename}[/b] username")
			password = Prompt.ask(f"[b]{servicename}[/b] password", password=True)
			token = utils.login(service, username, password)
			if token:
				console.print(f"Logged in, your token is [bold green]{token}[/bold green]")
			else:
				console.print(f"Error: Unable to authenticate to [b]{servicename}[/b]", style="red")
				return

		with console.status("[bold green]Checking token...") as status:
			check = utils.checktoken(service, token)
			if not check:
				console.print(f"[b]{servicename}[/b] log in generated an invalid token! Report this issue!", style="red")
				return
			else:
				utils.addtoken(userid, service, token)

	with console.status("[bold green]Fetching library...") as status:
		books = utils.library(service, token)

	if not books:
		console.print("No books!", style="bold red")
		return

	table = Table(title=f"Available books for {servicename}")
	table.add_column("Id", style="cyan")
	table.add_column("Internal id", style="magenta")
	table.add_column("Title", style="green")

	id2bookid = []
	downloadcovers = config.getboolean(service, "Cover", fallback=False)
	for (i, (bid, book)) in enumerate(books.items()):
		if downloadcovers:
			coverpath = utils.cover(service, token, bid, book)
		table.add_row(str(i), bid, book['title'])
		id2bookid.append(bid)

	console.clear()
	console.print(table)

	choices = Prompt.ask("Select a book or a comma-separated list of books").split(",")
	
	def checknumber(n):
		if n.isdigit():
			return int(n) < len(id2bookid)
		else:
			return False

	while not all(map(checknumber, choices)):
		choices = Prompt.ask("Invalid choice. Try again").split(",")

	for i in choices:
		bookid = id2bookid[int(i)]
		with Progress() as progress:
			maintask = progress.add_task("Starting...", total=100)
			def progressfun(update, status=""):
				if status:
					progress.update(maintask, description=status, completed=update)
				else:
					progress.update(maintask, completed=update)

			pdfpath = utils.downloadbook(service, token, bookid, books[bookid], progressfun)
			progress.update(maintask, description="Done", completed=100)

		console.print(f"[bold green]Done![/bold green] Your book is in {pdfpath}")

def downloadoneshot():
	if config.getboolean("pdfgrabber", "OneshotWarning", fallback=True):
		answer = Confirm.ask("[bold red]Oneshot services are unstable and lead to lower-quality books than normal services (they often have only pictures/unselectable text). Do you wish to continue?[/bold red]", default=False)
		if not answer:
			return
	service = selectservice(utils.oneshots)
	servicename = utils.oneshots[service]
	urlmatch = utils.geturlmatch(service)

	url = ""
	first = True
	while not re.fullmatch(urlmatch, url):
		if not first:
			console.print(f"Invalid url for {servicename}!", style="red")
		url = Prompt.ask(f"[b]{servicename}[/b] url")

	with Progress() as progress:
		maintask = progress.add_task("Starting...", total=100)
		def progressfun(update, status=""):
			if status:
				progress.update(maintask, description=status, completed=update)
			else:
				progress.update(maintask, completed=update)

		pdfpath = utils.downloadoneshot(service, url, progressfun)
		progress.update(maintask, description="Done", completed=100)

	console.print(f"[bold green]Done![/bold green] Your book is in {pdfpath}")

def register():
	username = Prompt.ask("Username")
	password = Prompt.ask("Password", password=True)
	repeatpassword = Prompt.ask("Retype password", password=True)
	if (password != repeatpassword):
		console.print("Passwords do not match!", style="bold red")
		exit()
	utils.register(username, password)
	console.print(f"Signed up {username}, now you can download books!", style="bold green")

def logout():
	global userid
	userid = False
	console.print("Logged out!", style="bold magenta")

def books():
	available = utils.listbooks()
	table = Table(title="Books")
	table.add_column("Service", style="cyan")
	table.add_column("Title", style="green")
	table.add_column("Pages", style="magenta")
	table.add_column("Path", style="blue")

	for i in available:
		table.add_row(i["service"], i["title"], str(i["pages"]), i["path"])

	console.print(table)

def main():
	if not (sys.version_info.major >= 3 and sys.version_info.minor >= 10):
		console.print("Python version 3.10 or greater is required!", style="bold red")
		exit()
	showbanner = config.getboolean("pdfgrabber", "ShowBanner", fallback=True)
	if showbanner:
		console.print(center(banner), style="green bold", no_wrap=True, highlight=False)
		console.print(Rule("version 1.0"))
	else:
		console.print(Rule("pdfgrabber version 1.0"))
	
	while True:
		action = Prompt.ask("[magenta]What do you want to do?[/magenta] ((r)egister new user, (d)ownload from your libraries, download from a (o)ne-shot link, (l)ogout, manage (t)okens, (v)iew all books, (q)uit)", choices=["r", "d", "o", "l", "t", "v", "q"], default="d")
		match action:
			case "r":
				register()
			case "d":
				downloadbook()
			case "o":
				downloadoneshot()
			case "l":
				logout()
			case "t":
				managetokens()
			case "v":
				books()
			case "q":
				console.print("Bye!", style="bold green")
				exit()
			case _:
				console.print("Invalid action!", style="bold red")
		console.print(Rule())

if __name__ == '__main__':
	try:
		main()
	except KeyboardInterrupt:
		console.print("\nBye!", style="bold green")
		try:
			sys.exit(0)
		except SystemExit:
			os._exit(0)
