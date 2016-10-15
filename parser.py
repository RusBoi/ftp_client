import argparse
from const import DOWNLOAD_DEFAULT_PATH, DEFAULT_PORT, DEFAULT_USERNAME


class Parser:
    @staticmethod
    def parse_arguments():
        parser = argparse.ArgumentParser(description="""ftp client server""")
        parser.add_argument('host', help='host to connect to')
        parser.add_argument('--port', '-p', type=int, help='port to connect to', default=DEFAULT_PORT)
        parser.add_argument('--user', '-u', help='username to login', default=DEFAULT_USERNAME)
        parser.add_argument('--passwd', help='password to login')
        parser.add_argument('--debug', help='debug mode', action="store_true")
        subparsers = parser.add_subparsers(title='commands to execute')

        parser_put = subparsers.add_parser('put', aliases=['upload'], help='upload file to the server')
        parser_put.add_argument('path1', help='path where file located on local machine')
        parser_put.add_argument('path2', nargs='?', default='.', help='path where file will be uploaded on the server')
        parser_put.set_defaults(func='put')

        parser_get = subparsers.add_parser('get', aliases=['download'], help='download file from the server')
        parser_get.add_argument('-r', action='store_true', help='download directory')
        parser_get.add_argument('path1', help='path where file located on the server')
        parser_get.add_argument('path2', nargs='?', default=DOWNLOAD_DEFAULT_PATH,
                                help='path where file will be stored on local machine')
        parser_get.set_defaults(func='get')

        parser_ls = subparsers.add_parser('ls', help='show content of remote directory')
        parser_ls.add_argument('path', help='path of the remote directory')
        parser_ls.set_defaults(func='ls')

        return parser.parse_args()