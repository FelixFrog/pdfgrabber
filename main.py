import utils
import version
import sys
import os
import shutil
import subprocess
import requests
import itamain
import ingmain
import re
from rich.console import Console
from rich.table import Table
from rich.rule import Rule
from rich.prompt import Prompt
from rich.prompt import Confirm
from rich.progress import Progress
import config

console = Console()

def center(var, space=None):
	return '\n'.join(' ' * int(space or (os.get_terminal_size().columns - len(var.splitlines()[len(var.splitlines()) // 2])) / 2) + line for line in var.splitlines())

def main():
	if not (sys.version_info.major >= 3 and sys.version_info.minor >= 10):
		console.print("Python version 3.10 or greater is required!", style="bold red")
		sys.exit(1)
	
	while True:
	
		action = Prompt.ask("Select a language: (ita)lian or (eng)lish", default="eng")
		match action:
			case "eng":
				ingmain.main()
				sys.exit(0)
			case "ita":
				itamain.main()
				sys.exit(0)

			case _:
				console.print('No "' + action + '" language!', style="bold red")


if __name__ == '__main__':
	try:
		main()
	except KeyboardInterrupt:
		console.print("\nBye!", style="bold green")
		try:
			sys.exit(0)
		except SystemExit:
			os._exit(0)
