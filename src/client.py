import functools
import getpass
import json
import os.path
import readline
import sys
import time
from parser import Parser
from shlex import split
from socket import timeout

from ftp import FTP, WrongResponse
from os import mkdir
from queue import Queue


def get_func(method: staticmethod):
    @functools.wraps(method.__func__)
    def wrapper(args):
        return method.__func__(args)
    return wrapper


with open('config.json') as f:
    config = json.load(f)


TIMEOUT_CODE = 421


class Client:
    ftp = None

    @staticmethod
    def setup(arguments):
        try:
            Client.ftp = FTP(
                arguments.host, arguments.port, callback=print,
                verbose_output=arguments.verbose)
        except KeyboardInterrupt:
            raise SystemExit

        if arguments.login is not None:
            username, password = arguments.login.split(':')
            Client.ftp.login(username, password)

        if hasattr(arguments, 'func'):
            if arguments.func == 'ls':
                a = ['-l', arguments.path]
            elif arguments.func == 'get' and arguments.r:
                a = ['-r', arguments.path1, arguments.path2]
            else:
                a = [arguments.path1, arguments.path2]

            Client.run_command(arguments.func, a)
            raise SystemExit

    @staticmethod
    def run():
        while True:
            try:
                tokens = split(input('ftp: '))
                if len(tokens) != 0:
                    command, *args = tokens
            except (KeyboardInterrupt, EOFError):
                Client.exit_handler([])
            else:
                Client.run_command(command, args)

    @staticmethod
    def run_command(command, args):
        """Sending command to the server with handling exceptions
        """
        if command not in Client.handlers:
            command = None
        try:
            Client.handlers[command](args)
        except WrongResponse as e:
            print('<<', e.response)
            if e.response.code == TIMEOUT_CODE:
                print('Trying to reconnect')
                Client.reconnect()
        except ValueError:
            Client.eprint('Wrong arguments. Use "help <command>"')
        except KeyboardInterrupt:
            print()
            pass
        except timeout:
            print('Timeout. Trying to reconnect')
            Client.reconnect()
        except ConnectionError:
            print(sys.exc_info()[1])
            print('Trying to reconnect')
            Client.reconnect()
        except:
            print(sys.exc_info()[1])

    @staticmethod
    def download_file(remote_path, local_path):
        data_length = 0
        start = time.time()
        for data in Client.ftp.get_file(remote_path):
            data_length += len(data)
            try:
                with open(local_path, 'ab') as file:
                    file.write(data)
            except:
                Client.eprint(sys.exc_info()[1])
                return

        result_time = time.time() - start
        speed = round(data_length / (1024 ** 2) / result_time, 4)
        info_string = (f'{data_length} bytes received in '
                       f'{round(result_time, 2)} secs ({speed} MB/s)')
        print(info_string)

    @staticmethod
    def download_directory(remote_path, local_path):
        if remote_path == '.':
            remote_path = ''

        dirs = Queue()
        dirs.put(remote_path)

        while not dirs.empty():
            remote_dir_path = dirs.get()
            local_dir_path = os.path.join(local_path, remote_dir_path)

            mkdir(local_dir_path)

            files = Client.ftp.list_files(remote_dir_path)

            for file, is_file in files:
                remote_file_path = os.path.join(remote_dir_path, file)
                local_file_path = os.path.join(local_path, remote_dir_path,
                                               file)
                if not is_file:
                    dirs.put(remote_file_path)
                else:
                    Client.download_file(remote_file_path, local_file_path)

    @staticmethod
    def eprint(*args, **kwargs):
        """Print message to the sys.stderr
        """
        print(*args, file=sys.stderr, **kwargs)

    @staticmethod
    def validate_path(path):
        """Return available directory's path by adding '*' symbol to the end
        :param path: initial path
        :return: validated path
        """
        while True:
            if os.path.isdir(path):
                path += '*'
            else:
                break
        return path

    @staticmethod
    def reconnect():
        args = Parser.parse_arguments()
        Client.setup(args)

    @staticmethod
    def upload_file(local_path, remote_path):
        try:
            with open(local_path, 'rb') as file:
                data = file.read()
        except:
            Client.eprint(sys.exc_info()[1])
        else:
            Client.ftp.upload_file(remote_path, data)

    # handlers

    @get_func
    @staticmethod
    def user_handler(args):
        """usage: user [<username> [<password>]]

        Send new user information. Default: anonymous
        """
        if len(args) == 0:
            args = [config['DEFAULT_USERNAME'], config['DEFAULT_PASS']]
        username = args[0]
        try:
            password = (args[1]
                        if len(args) > 1
                        else getpass.getpass('Enter password: '))
        except:
            print('Login failed')
        else:
            Client.ftp.login(username, password)

    @get_func
    @staticmethod
    def download_handler(args):
        """usage: get [-r] <remote_path> [<local_path>]

        Receive file from the server. If a file already exists then it will be
        overwritten. Also you can specify the directory's path where the file
        will be downloaded. Be sure to specify directory path.
        -r: receive whole directory from the server
        """
        if '-r' in args:
            method = Client.download_directory
            args = list(filter(lambda a: a != '-r', args))
        else:
            method = Client.download_file

        if len(args) == 0:
            raise ValueError
        if len(args) == 1:
            new_arg = config['DOWNLOAD_DEFAULT_PATH']
            if method == Client.download_file:
                new_arg = os.path.join(new_arg, os.path.split(args[0])[1])
            args.append(new_arg)
        args[1] = os.path.expanduser(args[1])
        if len(args) != 2:
            raise ValueError
        method(*args)

    @get_func
    @staticmethod
    def upload_handler(args):
        """usage: put <path1> [<path2>]

        Send file which is located in path1 to the server's path2.
        Path2 should be a directory
        """
        if not args:
            raise ValueError
        file_name = os.path.split(args[0])[-1]
        path2 = args[1] if len(args) > 1 else './'
        path2 = path2.rstrip('/')
        path2 = os.path.normpath(f'{path2}/{file_name}')
        Client.upload_file(args[0], path2)

    @get_func
    @staticmethod
    def remove_handler(args):
        """usage: rm <path>

        Remove file on the remote machine
        """
        if len(args) == 0:
            raise ValueError
        Client.ftp.remove_file(args[0])

    @get_func
    @staticmethod
    def pwd_handler(args):
        """Print current directory on remote machine
        """
        print(Client.ftp.get_current_location())

    @get_func
    @staticmethod
    def rename_handler(args):
        """usage: ren <file name>

        Rename file
        """
        if len(args) != 2:
            raise ValueError
        else:
            Client.ftp.rename_file(args[0], args[1])

    @get_func
    @staticmethod
    def cd_handler(args):
        """usage: cd <path>

        Change remote working directory
        """
        if not args:
            raise ValueError
        Client.ftp.change_directory(args[0])

    @get_func
    @staticmethod
    def mkdir_handler(args):
        """usage: mkdir <path>

        Make directory on the remote machine
        """
        if not args:
            raise ValueError
        Client.ftp.make_directory(args[0])

    @get_func
    @staticmethod
    def ls_handler(args):
        """usage: ls [-l] [<path>]

        Show content of remote directory
        -l: show content in list form
        """
        method = (Client.ftp._list_files
                  if '-l' in args
                  else Client.ftp.list_files)
        args = list(filter(lambda a: a != '-l', args))
        path = args[0] if len(args) == 1 else ''
        result = method(path)
        if isinstance(result, list):
            result = '\n'.join(map(
                lambda t: t[0] if t[1] else t[0] + '/',
                result))
        print(result)

    @get_func
    @staticmethod
    def size_handler(args):
        """usage: size <file_name>

        Show size of remote file
        """
        if not args:
            raise ValueError
        Client.ftp.get_size(args[0])

    @get_func
    @staticmethod
    def verbose_handler(args):
        """Toggle debugging mode
        """
        Client.ftp.verbose_output = not Client.ftp.verbose_output
        message = ('Verbose is on'
                   if Client.ftp.verbose_output
                   else 'Verbose is off')
        print(message)

    @get_func
    @staticmethod
    def switch_mode_handler(args):
        """Enter passive or active transfer mode
        """
        Client.ftp.passive_mode = not Client.ftp.passive_mode
        message = ('Passive mode is on'
                   if Client.ftp.passive_mode
                   else 'Active mode is on')
        print(message)

    @get_func
    @staticmethod
    def help_handler(args):
        """usage: help [<command>]

        Print local help information about command. If command isn't specified
        show all available commands
        """
        if not args:
            print('Commands: ')
            print((' ' * 4).join(sorted(filter(None, Client.handlers.keys()))))
        else:
            command = args[0]
            if command in Client.handlers:
                doc_lines = Client.handlers[command].__doc__.split('\n')
                for line in doc_lines:
                    print(line.strip())
            else:
                print(f'Unknown command "{command}".')

    @get_func
    @staticmethod
    def exit_handler(args):
        """Terminate ftp session
        """
        Client.ftp.quit()
        raise SystemExit

    @get_func
    @staticmethod
    def unknown_command_handler(args):
        """Handle unknown commands
        """
        print('Unknown command. Use "help"')

    handlers = {
        'get': download_handler,
        'put': upload_handler,
        'user': user_handler,
        'pwd': pwd_handler,
        'rm': remove_handler,
        'ren': rename_handler,
        'cd': cd_handler,
        'mkdir': mkdir_handler,
        'ls': ls_handler,
        'size': size_handler,
        'verbose': verbose_handler,
        'mode': switch_mode_handler,
        'help': help_handler,
        'exit': exit_handler,
        None: unknown_command_handler
    }


if __name__ == '__main__':
    args = Parser.parse_arguments()
    Client.setup(args)
    Client.run()
