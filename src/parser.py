import argparse
import json


with open('config.json') as f:
    config = json.load(f)


class Parser:
    @staticmethod
    def parse_arguments():
        parser = argparse.ArgumentParser(description="""ftp client server""")
        parser.add_argument('host', help='host to connect to')
        parser.add_argument('--port', '-p', type=int,
                            help='port to connect to',
                            default=config['DEFAULT_PORT'])
        parser.add_argument('--login',
                            help='login credentials (username:password)')
        parser.add_argument('--verbose', help='verbose', action="store_true")

        subparsers = parser.add_subparsers(title='commands to execute')

        parser_put = subparsers.add_parser(
            'put', help='upload file to the server')
        parser_put.add_argument(
            'path1', help="local file's path")
        parser_put.add_argument(
            'path2', nargs='?', default='.',
            help="remote file's path")
        parser_put.set_defaults(func='put')

        parser_get = subparsers.add_parser(
            'get', help='download file from the server')
        parser_get.add_argument('-r', action='store_true',
                                help='recursive download')
        parser_get.add_argument('path1', help="remote file's path")
        parser_get.add_argument(
            'path2', nargs='?', default=config['DOWNLOAD_DEFAULT_PATH'],
            help="local file's path")
        parser_get.set_defaults(func='get')

        parser_ls = subparsers.add_parser(
            'ls', help='show content of remote directory')
        parser_ls.add_argument('path', help="remote directory's path")
        parser_ls.set_defaults(func='ls')

        return parser.parse_args()
