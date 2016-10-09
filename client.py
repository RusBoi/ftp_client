import argparse
import ftplib
import getpass
import os.path
try:
    import readline
except:
    pass
import sys
import time
import traceback

from socket import timeout


DEFAULT_USERNAME = 'ftp'
DEFAULT_PASS = 'example@email.com'
DEFAULT_PORT = 21
TIMEOUT_CODE = 421
DOWNLOAD_DEFAULT_PATH = '~/Downloads/'


class FTPClient:
    def __init__(self):
        self.handlers = {
            'get': self.download_handler,
            'put': self.upload_handler,
            'user': self.user_handler,
            'pwd': self.pwd_handler,
            'rm': self.remove_handler,
            'ren': self.rename_handler,
            'cd': self.cd_handler,
            'mkdir': self.mkdir_handler,
            'ls': self.ls_handler,
            'size': self.size_handler,
            'debug': self.debug_handler,
            'mode': self.switch_mode_handler,
            'help': self.help_handler,
            'exit': self.exit_handler,
            None: self.unknown_command_handler
        }

        parser = argparse.ArgumentParser(description="""ftp client server""")
        parser.add_argument('host', help='host to connect to')
        parser.add_argument('--port', '-p', type=int, help='port to connect to', default=DEFAULT_PORT)
        parser.add_argument('--user', '-u', help='username to login', default=DEFAULT_USERNAME)
        parser.add_argument('--passwd', help='password to login')
        parser.add_argument('--debug', help='debug mode', action="store_true")
        subparsers = parser.add_subparsers(title='commands to execute')

        parser_put = subparsers.add_parser('put', aliases=['upload'], help='upload file to the server')
        parser_put.add_argument('path1', help='path where file located on local machine')
        parser_put.add_argument('path2', help='path where file will be uploaded on the server')
        parser_put.set_defaults(func='put')

        parser_get = subparsers.add_parser('get', aliases=['download'], help='download file from the server')
        parser_get.add_argument('path1', help='path where file located on the server')
        parser_get.add_argument('path2', nargs='?', default=DOWNLOAD_DEFAULT_PATH, help='path where file will be stored on local machine')
        parser_get.set_defaults(func='get')

        parser_ls = subparsers.add_parser('ls', help='show content of remote directory')
        parser_ls.add_argument('path', help='path of the remote directory')
        parser_ls.set_defaults(func='ls')

        args = parser.parse_args()

        try:
            host = args.host or input('Enter host name: ')
            self.ftp = ftplib.FTP(host, args.port, printout=print,
                                  print_output=args.debug, print_input=not hasattr(args, 'func'))
        except KeyboardInterrupt:
            print()
            raise SystemExit
        except:
            self.eprint(sys.exc_info()[1])
            raise SystemExit

        if args.user != DEFAULT_USERNAME and not args.passwd:
            self.run_command('user', [args.user])
        else:
            password = args.passwd or DEFAULT_PASS
            self.run_command('user', [args.user, password])

        if hasattr(args, 'func'):
            if args.func == 'ls':
                a = [args.path]
            else:
                a = [args.path1, args.path2]
            self.run_command(args.func, a)
            raise SystemExit

    def run(self):
        """
        Главный цикл
        """
        while True:
            try:
                command, *args = input('command: ').split(' ')
            except KeyboardInterrupt:
                print()
                self.exit_handler([])
            else:
                self.run_command(command, args)

    def run_command(self, command, args):
        if command not in self.handlers:
            command = None
        try:
            self.handlers[command](args)
        except ftplib.WrongResponse as e:
            print('<<', e.response)
            if e.response.code == TIMEOUT_CODE:
                # Если timeout то соединение восстановить не удастся и поэтому закроем клиент
                self.exit_handler([])
        except ValueError:
            self.eprint('Wrong arguments. Use "help <command>"')
        except KeyboardInterrupt:
            print()
            pass
        except timeout:
            print('Time out. Exiting program...')
            self.exit_handler([])

    def download_handler(self, args):
        """
        usage: get [-r] <path> [<directory_path>]
        Receive file from the server. If a file already exists then it will be overwritten.
        Also you can specify the directory's path where the file will be downloaded. Be sure to specify
        DIRECTORY path!
        optional arguments:
        -r\t\tReceive whole directory from the server
        """

        if not args or (args[0] == '-r' and len(args) == 1):
            raise ValueError
        if args[0] == '-r':
            pass
        else:
            path2 = args[1] if len(args) > 1 else DOWNLOAD_DEFAULT_PATH
            path2 = os.path.expanduser(path2)
            if not os.path.isdir(path2):
                self.eprint('"{}" is not a directory'.format(path2))
                raise ValueError
            path2 = os.path.normpath(path2 + '/' + os.path.split(args[0])[-1])
            if os.path.isfile(path2):
                os.remove(path2)
            self.download_file(args[0], path2)

    def download_file(self, path1, path2):
        """
        :param path1: server file's path to the file
        :param path2: destination file's path on the local machine
        """

        bytes_count = 0
        start = time.time()
        for data in self.ftp.download_file(path1):
            bytes_count += len(data)
            try:
                with open(path2, 'ab') as file:
                    file.write(data)
            except:
                self.eprint(sys.exc_info()[1])
                return

        result_time = time.time() - start
        speed = round(bytes_count / (1024 ** 2) / result_time, 4)
        info_string = '{} bytes received in {} secs ({} MB/s)'.format(bytes_count,
                                                                      round(result_time, 2),
                                                                      speed)
        print(info_string)

    def upload_handler(self, args):
        """
        usage: put [-r] <path1> [<path2>]
        Send file which is located in 'path1' to the server's 'path2'
        optional arguments:
        -r\t\tSend whole directory to the server
        """

        if not args or (args[0] == '-r' and len(args) == 1):
            raise ValueError
        if args[0] == '-r':
            pass
        else:
            file_name = os.path.split(args[0])[-1]
            path2 = args[1] if len(args) > 1 else './'
            path2 = os.path.normpath('{}/{}'.format(path2, file_name))
            self.upload_file(args[0], path2)

    def upload_file(self, path1, path2):
        """
        :param path1: local file's path
        :param path2: remote file's path
        """
        try:
            with open(path1, 'rb') as file:
                data = file.read()
        except:
            self.eprint(sys.exc_info()[1])
        else:
            self.ftp.upload_file(path2, data)

    def user_handler(self, args):
        """
        usage: user <username>
        Send new user information
        """

        if not args:
            raise ValueError
        username = args[0]
        try:
            password = args[1] if len(args) > 1 else getpass.getpass('Enter password: ')
        except:
            print()
            print('Login failed')
        else:
            self.ftp.login(username, password)

    def pwd_handler(self, args):
        """
        Print current directory on remote machine
        """

        self.ftp.get_location()

    def remove_handler(self, args):
        """
        usage: rm [-r] <path>
        Remove file on the remote machine
        optional arguments:
        -r\t\tremove directory
        """

        if not args or (args[0] == '-r' and len(args) == 1):
            raise ValueError
        if args[0] == '-r':
            self.ftp.remove_directory(args[1])
        else:
            self.ftp.remove_file(args[0])

    def rename_handler(self, args):
        """
        usage: ren <file name>
        Rename file
        """

        if len(args) != 2:
            raise ValueError
        else:
            self.ftp.rename_file(args[0], args[1])

    def cd_handler(self, args):
        """
        usage: cd <path>
        Change remote working directory
        """

        if not args:
            raise ValueError
        self.ftp.change_directory(args[0])

    def mkdir_handler(self, args):
        """
        usage: mkdir <directory name>
        Make directory on the remote machine
        """

        if not args:
            raise ValueError
        self.ftp.make_directory(args[0])

    def ls_handler(self, args):
        """
        usage: ls [-l] [<path>]
        Show content of remote directory
        opitonal arguments:
        -l\t\tShow content in list
        """

        if args:
            if args[0] == '-l':
                if len(args) > 1:
                    self.ftp.get_files(args[1])
                else:
                    self.ftp.get_files()
            else:
                self.ftp.get_filenames(args[0])
        else:
            self.ftp.get_filenames()

    def size_handler(self, args):
        """
        usage: size <file_name>
        Show size of remote file
        """

        if not args:
            raise ValueError
        self.ftp.get_size(args[0])

    def debug_handler(self, args):
        """
        Toggle debugging mode
        """

        if self.ftp.print_output:
            print('Debug is off')
        else:
            print('Debug is on')
        self.ftp.print_output = not self.ftp.print_output

    def switch_mode_handler(self, args):
        """
        Enter passive or active transfer mode
        """

        self.ftp.passive_state = not self.ftp.passive_state
        message = 'Passive mode is on' if self.ftp.passive_state else 'Active mode is on'
        print(message)

    def help_handler(self, args):
        """
        usage: help [<command>]
        Print local help information about command. If command isn't specified show all available commands
        """

        if not args:
            print('Commands: ')
            print('    '.join(filter(None, self.handlers.keys())))
        else:
            command = args[0]
            if command in self.handlers:
                for i in filter(None, self.handlers[command].__doc__.split('\n')):
                    print(i.lstrip())
            else:
                print('Unknown command "{}".'.format(command))

    def exit_handler(self, args):
        """
        Terminate ftp session and exit
        """
        print('Goodbye')
        self.ftp.close_connection()
        raise SystemExit

    def unknown_command_handler(self, args):
        print('Unknown command. Use "help"')

    def eprint(self, *args, **kwargs):
        """
        Printing to the sys.stderr
        :param args: some args
        :param kwargs: some args
        """

        print(*args, file=sys.stderr, **kwargs)


if __name__ == '__main__':
    f = FTPClient()
    f.run()
