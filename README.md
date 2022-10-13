# What is this?
This vendor-agnostic script is used to download pdfs (and covers) from different services.
# State of features
Every downloader has different features that might also be implemented in the future. As of now, there is a way to download best-quality pdf from every one of them, with varying degree of quality, speed and discretion. Here's a table riassuming all the features.

| service | pdf download | table of contents | pdf size | max logins | page labels | login expire | cover |
| ------- | :----------: | :---------------: | :------: | :--------: | :---------: | :----------: | :---: |
| scuolabook | perfect | yes (very small) | excellent | very restrictive | not yet/depends on vendor | never | yes |
| mylim | perfect | excellent | excellent | no | not yet/depends on vendor | ? | yes |
| pearson | perfect | (depends on vendor)/excellent | big | no | no/depends on vendor | never/? | yes |
| bsmart | yes | yes (very small) | very big (100+ mb) | no | not yet | ? | yes |
| hubyoung | yes | yes | very big (100+ mb) | no | not yet | ? | yes |
| macmillan | yes | yes (very small) | good/excellent | no/1token4ever | no | never | not yet |
| easyeschool | yes | yes (very small) | excellent | no/1token4ever | no | never | yes |
| zanichelli/booktab | yes | yes | good/average | yes | not yet | never | yes |
| zanichelli/kitaboo | yes | yes | average/big | yes | not yet | never | yes |

Apps that I am aware of but I can't work with them beacuse I don't have books:
 - Laterza diBooK (for the digital editions books there are already solutions)
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
## kitaboo books
For kitaboo books the script uses selenium and a chrome webdriver instance to rendere the html pages. It also uses a temporary directory that in my experience are sometimes buggy in python. If you plan on using that, make sure you have the required webdriver in your path (or follow selenium's official instructions [here](https://pypi.org/project/selenium/)). It might also not work at all on windows, I haven't had the opportunity to try it.
# How to use it
Just run ```python3 main.py```. You first need to create an account by selecting *r* in the first menu. The reason for this is that the script was intended to become a website and beacuse it is important to save the tokens and reduce the number of logins. After you created an account, select *d* and the menus will guide you. The output file will be ```files/<service>/<id>.pdf```
# Disclaimer
This script is provided "as is", without any type of warranty. I am not responsible of any harm or nuclear war that this may cause.