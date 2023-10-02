# What is this?
This vendor-agnostic script is used to download pdfs (and covers) from different services.
# State of features

| service | pdf download | table of contents | pdf size | max logins | page labels | login expire | cover | rendered | refershes tokens |
| ------- | :----------: | :---------------: | :------: | :--------: | :---------: | :----------: | :---: | :------: | :--------------: |
| Scuolabook | perfect | yes (very small) | excellent | very restrictive | yes | never | yes | no | no |
| MyLim | perfect | excellent | excellent | no | not yet/depends on vendor | ? | yes | no | no |
| Pearson+ / eText / Reader+ | perfect/yes | (depends on vendor)/excellent | big | no | yes/depends on vendor/no | ? | yes | sometimes | yes |
| bSmart / HoepliAcademy+ | yes | yes (very small) | very big (100+ mb) | no | yes | ? | yes | no | no |
| Mondadori HUB Scuola | yes | yes | very big (100+ mb) | no | yes (disable because glitches) | ? | yes | no | no |
| MEE2 / Blinklearning | yes | yes (very small) | good/excellent | no/1token4ever | no | never | yes | no | no |
| easyeschool | yes | yes (very small) | excellent | no/1token4ever | no | never | yes | no | no |
| Zanichelli Booktab | yes | yes | good/average | yes | yes | ? | yes | no | no |
| Zanichelli Kitaboo | yes | yes | average/big | yes | yes | ? | yes | yes | no |
| Oxford Learner’s Bookshelf | yes | yes (small) | very big | ? | not yet/no | ? | yes | no | no |
| Laterza diBooK | yes | yes/(depends on vendor) | excellent | ? | not yet/no | ? | yes | no | no |
| Raffaello Player | yes | yes (incomplete bc no samples :-( | very big | ? | yes | ? | yes | no | no |
| Cambridge GO | yes | yes | big | no | yes | yes | yes | yes | no |

Apps that I am aware of but I can't work with beacuse I don't have books:
 - Appbook (might be a shitty html webview)
 - Digimparo (giuntitvp instance)
 - Vitalsource (american platform, very good protection)
 - digibook24 ("The platform was developed by bsmartlabs"?)

## TODO
 - Add anonymous user
 - ~~Add ability to pass options to scripts~~
 - Add "perfect" token checks
 - General code quality improvement (better management of exceptions)
 - Make toc and labels generation raise non-critical warnings

# Installation
1. download the latest version of [Python](https://www.python.org/downloads/)
    - on windows, when installing though the set up wizard, make sure to select the checkbox to add python to `PATH`
    - on linux and macos, use your package manager of choice (`brew install python3` or `apt install python3`, etc...)
2. downlaod the pdfgrabber repo
    - using git: `git clone https://github.com/FelixFrog/pdfgrabber.git`
    - manually: download the zip (green button labeled "code") and extract it
3. open your local clone of pdfgrabber
4. open the terminal in that directory and run:
    1) `pip install -r requirements.txt` (takes care of installing every needed libraries)
    2) run the script
        - `python3 main.py` (linux and macos) 
        - `py main.py` (windows)
5. once inside the pdfgrabber CLI:
    - press `r`: register a new account
    - choose what to do (it's listed):
       - to download a book: press `d` and follow the instructions.
       - the output file will be `files/<service>/<id>.pdf`

# Quirks
## Scuolabook
Scuolabook has a very strict login system, where you can have only 2 devices logged in and you only have 2 deletions per year. This means that you can only log in 4 times every year, with no way of downloading books (at least, the pdf version) if you have hit this limit. pdfgrabber should save the token for you, but you should also keep it somewhere safer such as a text document. 
## Pearson
Both RPLUS_PDF and RPLUS_EPUB books are stored in a password protected zip file. Python's ZipFile module doesn't do the decryption natively, so it might take a (very) long time for some big books in the "Extracting zip" phase. If you have found a decent workaround let me know.
# Support
For personalized support, contact me on [telegram](https://t.me/fflxx).
We also accept donations, so we can keep this project up! 

[![liberapay](https://liberapay.com/assets/widgets/donate.svg)](https://liberapay.com/flx/donate)

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/Z8Z4PCZUI)

Also [Satispay](https://www.satispay.com/app/match/link/user/S6Y-CON--A7BC8CDF-2EF5-40B7-884C-FDAB482CA8ED)


# Disclaimer
This script is provided "as is", without any type of warranty. I am not responsible of any harm or nuclear war that this may cause.
