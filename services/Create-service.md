# Service description

.login(username, password) -> token

.downloadbook(token, bookid, data, progress) -> pdf

.cover(token, bookid, data) -> raw image data

.library(token) -> [bookid: {"title": title}]

.checktoken(token) -> Boolean

.refreshtoken(refreshtoken) -> new token
