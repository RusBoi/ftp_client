import argparse
import ftplib
import getpass
try:
    import readline
except:
    pass
import os.path
import sys

from socket import timeout
from enum import Enum


DEFAULT_USERNAME = 'ftp'
DEFAULT_PASS = 'example@email.com'
DEFAULT_PORT = 21
TIMEOUT_CODE = 421


class FTPClient:
    def __init__(self):
        parser = argparse.ArgumentParser(description="""Ftp client server""")
        parser.add_argument('--host', help='Host to connect to')
        parser.add_argument('--port', '-p', type=int, help='Port to connect to')
        parser.add_argument('--user', '-u', help='Username to login')
        parser.add_argument('--passwd', help='Password to login')
        parser.add_argument('--debug', help='Debug mode', action="store_true")
        args = parser.parse_args()

        try:
            host = args.host or input('Enter host name: ')
            port = args.port or DEFAULT_PORT
            self.ftp = ftplib.FTP(host, port, printout=print)
            self.ftp.debug = args.debug
        except KeyboardInterrupt:
            print()
            raise SystemExit
        except:
            self.eprint(sys.exc_info()[1])
            raise SystemExit

        try:
            username = args.user or DEFAULT_USERNAME
            if username != DEFAULT_USERNAME and not args.passwd:
                # пользователь ввел свой логин, но хочет ввести пароль скрытно
                self.user_handler([username])
            else:
                password = args.passwd or DEFAULT_PASS
                self.user_handler([username, password])
        except ftplib.WrongResponse as e:
            print('<<', e.response)
        except:
            self.eprint(sys.exc_info()[1])

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
            'exit': self.exit_handler
        }

    def run(self):
        """
        Главный цикл
        """
        while True:
            try:
                command, *args = input().split(' ')
            except KeyboardInterrupt:
                print()
                self.exit_handler([])
            else:
                if command not in self.handlers:
                    print('Unknown command. Use "help"')
                else:
                    try:
                        self.handlers[command](args)
                    except ftplib.WrongResponse as e:
                        print('<<', e.response)
                        if e.response.code == TIMEOUT_CODE:
                            # Если timeout то соединение восстановить не удастся и поэтому закроем клиент
                            self.exit_handler([])
                    except ValueError:
                        self.eprint('Wrong arguments. Use "help <command>"')
                    except SystemExit:
                        raise SystemExit
                    except KeyboardInterrupt:
                        print()
                        pass
                    except timeout:
                        print('Time out. Use "exit".')
                    except:
                        self.eprint(sys.exc_info()[1])

    def download_handler(self, args):
        """
        usage: get [-r] <path>
        Receive file from the server
        optional arguments:
        -r\t\tReceive whole directory from the server
        """

        if not args or (args[0] == '-r' and len(args) == 1):
            raise ValueError
        if args[0] == '-r':
            pass
        else:
            self.download_file(args[0])

    def download_file(self, file_path):
        file_name = os.path.split(file_path)[-1]
        data = self.ftp.download_file(file_path)
        try:
            with open(file_name, 'wb') as file:
                file.write(data)
        except:
            self.eprint(sys.exc_info()[1])

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
            self.upload_file(*args[:2])

    def upload_file(self, path1, path2=None):
        file_name = os.path.split(path1)[-1]
        if path2:
            dest_path = os.path.normpath('{}/{}'.format(path2, file_name))
        else:
            dest_path = file_name

        try:
            with open(path1, 'rb') as file:
                data = file.read()
        except:
            self.eprint(sys.exc_info()[1])
        else:
            self.ftp.upload_file(dest_path, data)

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

        if self.ftp.debug:
            print('Debug is off')
        else:
            print('Debug is on')
        self.ftp.debug = not self.ftp.debug

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
            print('    '.join(self.handlers.keys()))
        else:
            command = args[0]
            if command in self.handlers:
                print(self.handlers[command].__doc__)
            else:
                print('Unknown command "{}".'.format(command))

    def exit_handler(self, args):
        """
        Terminate ftp session and exit
        """
        print('Goodbye')
        self.ftp.close_connection()
        raise SystemExit

    def eprint(self, *args, **kwargs):
        print(*args, file=sys.stderr, **kwargs)


if __name__ == '__main__':
    f = FTPClient()
    f.run()
