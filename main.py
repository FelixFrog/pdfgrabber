import utils
import version
import sys
import os
import shutil
from git import Repo
import subprocess
import requests
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

def center(var, space=None):
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
	console.clear()

	table = Table(title="Available services")
	table.add_column("Code", style="cyan")
	table.add_column("Name", style="green")

	for code, name in services.items():
		table.add_row(code, name)

	console.print(table)

	chosenone = Prompt.ask("Choose a service", choices=services.keys())
	
	return chosenone

def managetokens():
	if not userid:
		login()
	table = Table(title="Tokens")
	table.add_column("Service", style="cyan")
	table.add_column("Token", style="green")

	for service in utils.services:
		token = utils.gettoken(userid, service)
		table.add_row(service, token[:20] + "..." if len(token or "") > 23 else "")

	console.clear()
	console.print(table)

	servicenow = Prompt.ask("Choose a service to delete the token from", choices=utils.services.keys())
	utils.deletetoken(servicenow, userid)
	console.print(f"Token for [bold]{servicenow}[/bold] deleted!")

def downloadbook():
	global userid
	if not userid:
		if not len(utils.getusers()) == 0:
			login()
		else:
			console.print('[b]No user was created! Use "r" for creating an user then try again.[/b]')
			return

	console.clear()

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

	choices = Prompt.ask("Select a book or a comma-separated list of books").split(",")
	
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
		choices = Prompt.ask("Invalid choice. Try again").split(",")


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
		console.print(f"[bold green]Book downloaded![/bold green] Your book is in {pdfpath}")

def clone_and_restart(repo_url):
    local_path = "temp_repo"
    Repo.clone_from(repo_url, local_path)


    current_dir = os.path.dirname(os.path.realpath(__file__))
    for item in os.listdir(local_path):
        item_path = os.path.join(local_path, item)
        if os.path.isdir(item_path):
            shutil.copytree(item_path, os.path.join(current_dir, item), dirs_exist_ok=True)
        else:
            shutil.copy2(item_path, current_dir)

    shutil.rmtree(local_path)

    python = sys.executable
    subprocess.call([python, "main.py"])

def updates():
	# replace this url when done
	ur = requests.get("https://raw.githubusercontent.com/ErricoV1/pdfgrabber/zanichellitakedown/version.py")
	urt = ur.text
	latestversion = urt.split('version = "')[1].split('"')[0]

	# THIS is the killswitch.
	# The author can use this lever to interrupt usage of the tool.
	# Removing this means that you can be held liable for damages to boo authors.
	if latestversion == "KILL":
		console.print(center("Service currently unavailable for unknown reasons."), style="white bold")
		sys.exit(20)

	if latestversion != version:
		console.print(center('This version is not the most recent one!'), style="yellow bold")
		console.print(center('Updating from ' + version + ' to ' + latestversion + '...'), style="yellow bold")
		updated = False
	else:
		updated = True
	return updated

def downloadoneshot():
	console.clear()
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
		console.print(Rule("version " + version))
		console.print(center("WARNING! Read the disclaimer before using the tool!"), style="red bold italic")
	else:
		console.print(Rule("pdfgrabber version " + version))

	isUpdated = updates()

	if not isUpdated:
		clone_and_restart()
	
	while True:
		action = Prompt.ask("[magenta]What do you want to do?[/magenta] ((r)egister new user, (d)ownload from your libraries, download from a (o)ne-shot link, (l)ogout, manage (t)okens, (v)iew all books, (q)uit)", default="d")
		match action:
			case "v":
				books()
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
