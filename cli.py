import argparse
import utils
import getpass

services = utils.services.keys()

def main():
	dparser = argparse.ArgumentParser(prog='pdfgrabber', description='Vendor-agnostic script to download books in pdf format')
	dparser.add_argument('--version', action='version', version='%(prog)s 1.0')
	dparser.add_argument('-s', '--service', choices=services, required=True, help='the service to download books from')

	idgroup = dparser.add_mutually_exclusive_group(required=True)
	idgroup.add_argument('-t', '--token', help='the token for the service selected')
	idgroup.add_argument('-u', '--username', help='the username for the service selected')

	dparser.add_argument('-p', '--password', help='the password for the specified username, consumed from stdin if necessary but not specified')

	dparser.add_argument('books', nargs='+', type=str, help='the bookids of the book to download')
	dparser.add_argument('-o', '--outfile', nargs='?', type=argparse.FileType('wb'), help='the file to write the output to')
	dparser.add_argument('-q', '--quiet', action='store_true', help='don\'t show during the download process')
	args = dparser.parse_args()

	def progress(perc, message=''):
		if not args.quiet:
			percs = str(round(perc)).zfill(2)
			print(f'[{percs}%] {message}')

	if token := args.token:
		progress(0, 'Checking token')
		if not utils.checktoken(args.service, token):
			print('Invalid token')
			exit()
	else:
		if not (password := args.password):
			password = getpass.getpass(f'Enter password for {args.username}@{args.service}: ')
			progress(0, 'Logging in')
		token = utils.login(args.service, args.username, password)
		if not token:
			print('Could not login')
			exit()
		else:
			progress(0, 'Logged in, obtained token:')
			print(token)

	library = utils.library(args.service, token)
	books = [(k, v['title']) for k, v in library.items()]
	progress(0, 'Books available:')
	for i in books:
		print(f'\t{i[0]}: {i[1]}')

	service = utils.getservice(args.service)
	for b in args.books:
		if not b in library:
			print(f'Skipping book {b}, not in library!')
			continue
		try:
			pdf = service.downloadbook(token, b, library[b], progress)
		except Exception as e:
			print(f'Error while downloading {b}')
			print(e)
			continue
		if not (output := args.outfile):
			output = open(f'{args.service}-{b}.pdf', 'wb')
		pdf.ez_save(output)

if __name__ == '__main__':
	main()
