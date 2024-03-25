# What is this?
This vendor-agnostic script is used to download pdfs (and covers) from different services.

# Disclaimer
This script is provided "as is", without any type of warranty. I am not responsible of any harm or nuclear war that this may cause.
Even though this script exists, you are responsibile of the PDFs generated. Check if the backup of books is legal in your country.
Redistribution of PDFs is highly discouraged and not supported by the Author.

Please contact me on "Issues" if you want to issue a takedown notice.

# State of features

| service | pdf download | table of contents | pdf size | max logins | page labels | login expire | cover | rendered | refershes tokens | additional information |
| ------- | :----------: | :---------------: | :------: | :--------: | :---------: | :----------: | :---: | :------: | :--------------: | :--------------------: |
| MyLim | perfect | excellent | excellent | no | not yet/depends on vendor | ? | yes | no | no | |
| Pearson Reader+ / Pearson+ | perfect/yes | (depends on vendor)/excellent | big | no | yes/depends on vendor/no | ? | yes | sometimes | yes | decryption of zip file takes a lot: contact me if you have found a workaround. |
| bSmart / HoepliAcademy+ | yes | yes (very small) | very big (100+ mb) | no | yes | ? | yes | no | no | |
| Mondadori HUB Scuola | yes | yes | very big (100+ mb) | no | yes (disable because glitches) | ? | yes | no | no | |
| MEE2 / Blinklearning | yes | yes (very small) | good/excellent | no/1token4ever | no | never | yes | no | no | |
| easyeschool | yes | yes (very small) | excellent | no/1token4ever | no | never | yes | no | no | |
| Oxford Learner’s Bookshelf | yes | yes (small) | very big | ? | not yet/no | ? | yes | no | no | |
| Laterza diBooK | yes | yes/(depends on vendor) | excellent | ? | not yet/no | ? | yes | no | no | |
| Raffaello Player | yes | yes | very big | ? | yes | ? | yes | no | no | |
| Cambridge GO | yes | yes | big | no | yes | yes | yes | yes | no | |
| Palumbo Editore - Saggi Digitali | yes | yes | average/big | no | no | no | yes | no | no | |
| Cengage Read | yes | yes | enormous (500+ mb) | no | yes | ? | yes | yes | yes | |
| Oxford Reading Club | yes | yes/(depends on vendor) | big | 2 | no | ? | yes | no | no | |

Apps that I am aware of but I can't work with beacuse I don't have books:
 - ~~Appbook (might be a shitty html webview)~~
 - Digimparo (giuntitvp instance)
 - Vitalsource (american platform, very good protection)
 - digibook24 ("The platform was developed by bsmartlabs"?)
 - Edisco Flowbook (more giuntitvp-like garbage?)

## TODO
 - Make a CLI interface with argparser
 - Token versioning
 - pdfgrabber versining
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
       - the output file will be `files/<service>/<book name>.pdf`

# Services that were once supported but now aren't
## Zanichelli services
An [unformal takedown notice from Zanichelli](https://github.com/FelixFrog/pdfgrabber/issues/75) was issued.
## Scuolabook
Scuolabook has shutdown on 01/01/2024

# Support
For personalized support, contact me on [telegram](https://t.me/fflxx).
We also accept donations, so we can keep this project up! 

[![liberapay](https://liberapay.com/assets/widgets/donate.svg)](https://liberapay.com/flx/donate)

[![ko-fi](https://ko-fi.com/img/githubbutton_sm.svg)](https://ko-fi.com/Z8Z4PCZUI)

Also [Satispay](https://www.satispay.com/app/match/link/user/S6Y-CON--A7BC8CDF-2EF5-40B7-884C-FDAB482CA8ED)


