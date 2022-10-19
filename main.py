import utils
import sys
import os
from rich.console import Console
from rich.table import Table
from rich.rule import Rule
from rich.prompt import Prompt
from rich.prompt import Confirm

console = Console()
userid = ""

def login():
	global userid
	username, password = "", ""
	first = True
	while not (userid := utils.new_login(username, password)):
		if not first:
			console.print("Invalid login!", style="red")
		first = False
		username = Prompt.ask("[b]pdfgrabber[/b] username")
		password = Prompt.ask("[b]pdfgrabber[/b] password", password=True)
	console.print("Logged in!", style="green")

def selectservice():
	table = Table(title="Avaliable services")
	table.add_column("Code", style="cyan")
	table.add_column("Name", style="green")

	for code, name in utils.services.items():
		table.add_row(code, name)

	console.print(table)

	return Prompt.ask("Choose a service", choices=utils.services.keys())

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
	if not userid:
		login()

	service = selectservice()
	token = utils.gettoken(userid, service)
	servicename = utils.services[service]
	
	if token:
		with console.status("[bold green]Checking token...") as status:
			check = utils.checktoken(service, token)
			if not check:
				token = ""

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
				exit()

		with console.status("[bold green]Checking token...") as status:
			check = utils.checktoken(service, token)
			if not check:
				exit()
			else:
				utils.addtoken(userid, service, token)

	with console.status("[bold green]Fetching library...") as status:
			books = utils.library(service, token)

	table = Table(title=f"Avaliable books for {servicename}")
	table.add_column("Id", style="cyan")
	table.add_column("Internal id", style="magenta")
	table.add_column("Title", style="green")

	id2bookid = []
	for (i, (bid, book)) in enumerate(books.items()):
		coverpath = utils.cover(service, token, bid, book)
		table.add_row(str(i), bid, book['title'])
		id2bookid.append(bid)

	console.clear()
	console.print(table)

	bookid = id2bookid[int(Prompt.ask("Select a book", choices=[str(i) for i in range(len(id2bookid))]))]

	from rich.progress import Progress
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
	console.print("Logged out!", style="bold magenta")

def books():
	avaliable = utils.listbooks()
	table = Table(title="Books")
	table.add_column("Service", style="cyan")
	table.add_column("Title", style="green")
	table.add_column("Pages", style="magenta")
	table.add_column("Path", style="blue")

	for i in avaliable:
		table.add_row(i["service"], i["title"], str(i["pages"]), i["path"])

	console.print(table)

def main():
	if not (sys.version_info.major >= 3 and sys.version_info.minor >= 10):
		console.print("Python version 3.10 or greater is required!", style="bold red")
		exit()
	console.print(Rule("pdfgrabber 1.0"))
	while True:
		action = Prompt.ask("[magenta]What do you want to do?[/magenta] (register new user, download a book, logout, manage tokens, view all books, quit)", choices=["r", "d", "t", "l", "b", "q"], default="d")
		match action:
			case "r":
				register()
			case "d":
				downloadbook()
			case "l":
				logout()
			case "t":
				managetokens()
			case "b":
				books()
			case "q":
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
