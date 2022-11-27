import configparser
from pathlib import Path
import os
import shutil

os.chdir(Path(__file__).parent)

def getconfig():
	config = configparser.ConfigParser()
	conffile = Path("config.ini")
	if not conffile.is_file():
		shutil.copyfile(Path("config-default.ini"), conffile)
	config.read_file(open(conffile))
	return config