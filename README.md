# What is this?
This vendor-agnostic script is used to download pdfs (and covers) from different services.
# State of features
Every downloader has different features that might also be implemented in the future. As of now, there is a way to download best-quality pdf from every one of them, with varying degree of quality, speed and discretion. Here's a table riassuming all the features.

| service | pdf download | table of contents | pdf size | max logins | page labels | login expire | cover | redered |
| ------- | :----------: | :---------------: | :------: | :--------: | :---------: | :----------: | :---: | :-----: |
| Scuolabook | perfect | yes (very small) | excellent | very restrictive | not yet/depends on vendor | never | yes | no |
| MyLim | perfect | excellent | excellent | no | not yet/depends on vendor | ? | yes | no |
| Pearson eText | perfect | (depends on vendor)/excellent | big | no | no/depends on vendor | very fast (30 min) | yes | sometimes |
| Pearson Reader+ | yes | good/very good | big | no | no/depends on vendor | very fast (30 min) | yes | no |
| bSmart | yes | yes (very small) | very big (100+ mb) | no | not yet | ? | yes | no |
| Mondadori Hub Young | yes | yes | very big (100+ mb) | yes (disable because glitches) | not yet | ? | yes | no |
| MEE2 | yes | yes (very small) | good/excellent | no/1token4ever | no | never | yes (?) | no |
| easyeschool | yes | yes (very small) | excellent | no/1token4ever | no | never | yes | no |
| Zanichelli Booktab | yes | yes | good/average | yes | yes | ? | yes | no |
| Zanichelli Kitaboo | yes | yes | average/big | yes | yes | ? | yes | yes |
| Oxford Learner’s Bookshelf | yes | yes (small) | very big | ? | not yet/no | ? | yes | no |
| Laterza diBooK | yes | yes/(depends on vendor) | excellent | ? | not yet/no | ? | yes | no |

Apps that I am aware of but I can't work with beacuse I don't have books:
 - Raffaello player
 - Appbook (might be a shitty html webview like booktab)

## TODO
 - Add anonymous user
 - Add ability to pass options to scripts
 - Add page labels and perfect token checks
 - General code quality improvement (better management of exceptions)
 - Use pathlib for better windows compatibility

# Installation
You need python 3.6+. To install all the requirements run ```python3 -m pip install -r requirements.txt```. Also the script has been tested only on mac os, contact me if you have tried it on linux/windows or you have problems.
## Kitaboo/Reader+ books
For kitaboo books the script uses selenium and a chrome webdriver instance to rendere the html pages. It might also not work at all on windows, I haven't had the opportunity to try it. To configure it, go to ```lib.py``` and change the two paths at the beginning of the file, one for the chromedriver executable path, the other with the chrome binary path.
# How to use it
Just run ```python3 main.py```. You first need to create an account by selecting *r* in the first menu. After you created an account, select *d* and the menus will guide you. The output file will be ```files/<service>/<id>.pdf```
# Disclaimer
This script is provided "as is", without any type of warranty. I am not responsible of any harm or nuclear war that this may cause.
