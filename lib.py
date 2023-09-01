import re

roman = [(1000, "M"), (900, "CM"), (500, "D"), (400, "CD"), (100, "C"), (90, "XC"), (50, "L"), (40, "XL"), (10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]

def generatelabelsrule(labels):
	rules = []
	guessed = False
	for i, label in enumerate([str(j).strip() for j in labels]):
		estimated = estimatelabel(label)
		if label != guessed:
			rules.append(estimated | {"startpage": i})
		estimated["firstpagenum"] += 1
		guessed = createlabel(estimated)
	return rules

def estimatelabel(label):
	# {"style": "D|r|R|a|A", "prefix": "", "firstpagenum": 0}
	if re.fullmatch("[0-9]+", label) and label != "0" and str(int(label)) == label:
		return {"style": "D", "prefix": "", "firstpagenum": int(label)}
	elif m := re.fullmatch("([^0-9]+?)([0-9]+)", label):
		return {"style": "D", "prefix": m.group(1), "firstpagenum": int(m.group(2))}
	elif (m := re.fullmatch("(?<=^)(M{0,}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})|m{0,}(cm|cd|d?c{0,3})(xc|xl|l?x{0,3})(ix|iv|v?i{0,3}))(?=$)", label)) and len(label) > 0:
		return {"style": "R" if label.isupper() else "r", "prefix": "", "firstpagenum": destroyroman(m.group(0))}
	else:
		return {"style": "", "prefix": label, "firstpagenum": 0}
	# Disable these three modes beacuse they are buggy and very rare
	'''
	elif m := re.fullmatch("(?<=^)(.+?)(?!$)(M{0,}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})|m{0,}(cm|cd|d?c{0,3})(xc|xl|l?x{0,3})(ix|iv|v?i{0,3}))(?=$)", label):
		return {"style": "R" if m.group(2).isupper() else "r", "prefix": m.group(1), "firstpagenum": destroyroman(m.group(2))}
	# These two are completely broken, NEVER enable them
	elif m := re.fullmatch("[a-z]+|[A-Z]+", label):
		return {"style": "A" if label.isupper() else "a", "prefix": "", "firstpagenum": destroyalphabetical_fake(label)}
	elif m := re.fullmatch("(?<=^)(.+?)(?!$)([a-z]+|[A-Z]+)(?=$)", label):
		return {"style": "A" if m.group(2).isupper() else "a", "prefix": m.group(1), "firstpagenum": destroyalphabetical_fake(m.group(2))}
	'''

def createlabel(rule):
	match rule["style"]:
		case "D":
			return rule["prefix"] + str(rule["firstpagenum"])
		case "r" | "R":
			s = buildroman(rule["firstpagenum"])
			return rule["prefix"] + (s if rule["style"].isupper() else s.lower())
		case "a" | "A":
			s = buildalphabetical(rule["firstpagenum"])
			return rule["prefix"] + (s.upper() if rule["style"].isupper() else s)
		case _:
			return rule["prefix"]

def buildroman(n):
	a = n
	s = ""
	while a > 0:
		for i, j in roman:
			k, l = divmod(a, i)
			s += j * k
			a = l

	return s

def buildalphabetical(n):
	ls = [chr(i) for i in range(97, 97 + 26)]
	t, r = divmod(n, 26)
	return ls[r + 1] * (t + 1)

def destroyalphabetical(s):
	t = len(s) - 1
	r = ord(s[0]) - 96
	return 26 * t + r


def buildalphabetical_fake(n):
	ls = [chr(i) for i in range(65, 65 + 26)]

	i, a = 1, n
	s = ""
	while 26 ** i <= a:
		a -= 26 ** i
		i += 1

	for j in reversed(range(i)):
		f, a = divmod(a, 26 ** j)
		s += ls[f]
	return s

def destroyroman(s):
	t = s.upper()
	if not re.fullmatch("M{0,}(CM|CD|D?C{0,3})(XC|XL|L?X{0,3})(IX|IV|V?I{0,3})", t):
		raise ValueError(f"The string {s} is not a valid roman numeral!")
	n = 0
	while len(t) > 0:
		for i, j in roman:
			if t.startswith(j):
				t = t.removeprefix(j)
				n += i

	return n

def destroyalphabetical_fake(s):
	t = s.lower()
	if not re.fullmatch("[a-z]+", t):
		raise ValueError(f"The string {s} is not a valid alphabetical page!")
	n = 0
	for i, l in enumerate(reversed(t)):
		n += int(26 ** i * (ord(l) - 96))

	return n - 1