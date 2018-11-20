import const
import ftplib
import functools
import getpass
import os.path
try:
    import readline
finally:
    pass
import sys
import time

from parser import Parser
from shlex import split
from socket import timeout


def get_func(method: staticmethod):
    @functools.wraps(method.__func__)
    def wrapper(args):
        return method.__func__(args)
    return wrapper


class FTPClient:
    ftp = None
    current_directory = '/'

    @staticmethod
    def connect(arguments):
        try:
            host = arguments.host or input('Enter host name: ')
            FTPClient.ftp = ftplib.FtpClient(host, arguments.port, printout=print,
                                       print_output=arguments.debug, print_input=not hasattr(arguments, 'func'))
        except KeyboardInterrupt:
            print()
            raise SystemExit
        except:
            FTPClient.eprint(sys.exc_info()[1])
            raise SystemExit

        if arguments.user != const.DEFAULT_USERNAME and not arguments.passwd:
            FTPClient.run_command('user', [arguments.user])
        else:
            password = arguments.passwd or const.DEFAULT_PASS
            FTPClient.run_command('user', [arguments.user, password])

        if hasattr(arguments, 'func'):
            if arguments.func == 'ls':
                a = ['-l', arguments.path]
            elif arguments.func == 'get' and arguments.r:
                a = ['-r', arguments.path1, arguments.path2]
            else:
                a = [arguments.path1, arguments.path2]

            FTPClient.run_command(arguments.func, a)
            raise SystemExit

    @staticmethod
    def run():
        """
        Main cycle
        """
        while True:
            try:
                # command, *args = input('command: ').split(' ')
                command, *args = split(input('command: '))
            except KeyboardInterrupt:
                print()
                FTPClient.exit_handler([])
            else:
                FTPClient.run_command(command, args)

    @staticmethod
    def run_command(command, args):
        """
        Sending(running) command to the server with handling exceptions
        :param command: command to run
        :param args: arguments
        """
        if command not in FTPClient.handlers:
            command = None
        try:
            FTPClient.handlers[command](args)
        except ftplib.WrongResponse as e:
            print('<<', e.response)
            if e.response.code == const.TIMEOUT_CODE:
                print('Trying to reconnect')
                FTPClient.reconnect()
        except ValueError:
            FTPClient.eprint('Wrong arguments. Use "help <command>"')
        except KeyboardInterrupt:
            print()
            pass
        except timeout:
            print('Time out')
            print('Trying to reconnect')
            FTPClient.reconnect()
        except ConnectionError:
            print(sys.exc_info()[1])
            print('Trying to reconnect')
            FTPClient.reconnect()
        else:
            # если не возникло никаких ошибок при переходе в новую директорию, то запоминаем ее как текущую
            if command == 'cd' and args:
                FTPClient.current_directory = args[0]

    @get_func
    @staticmethod
    def download_handler(args):
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
            path1 = args[1].rstrip('/') or '/'
            dirname = 'ftp-server' if path1 == '/' else os.path.split(path1)[-1]

            if len(args) > 2:
                path2 = os.path.expanduser(args[2])
            else:
                path2 = os.path.expanduser(const.DOWNLOAD_DEFAULT_PATH)
            if not os.path.isdir(path2):
                FTPClient.eprint('"{}" is not a directory'.format(path2))
                raise ValueError

            path2 = FTPClient.validate_path(path2.rstrip('/') + '/' + dirname)

            try:
                os.mkdir(path2)
            except:
                FTPClient.eprint(sys.exc_info()[1])
                return

            # замьютим все сообщения
            old_in, old_out = FTPClient.ftp.print_input, FTPClient.ftp.print_output
            FTPClient.ftp.print_input = False
            FTPClient.ftp.print_output = False

            FTPClient.download_directory(path1, path2)
            # вернем сообщения обратно
            FTPClient.ftp.print_input, FTPClient.ftp.print_output = old_in, old_out
        else:
            path1 = args[0].rstrip('/')

            path2 = args[1] if len(args) > 1 else const.DOWNLOAD_DEFAULT_PATH
            path2 = os.path.expanduser(path2)
            if not os.path.isdir(path2):
                FTPClient.eprint('"{}" is not a directory'.format(path2))
                raise ValueError
            path2 = path2.rstrip('/') + '/' + os.path.split(path1)[-1]
            if os.path.isfile(path2):
                os.remove(path2)

            FTPClient.download_file(path1, path2)

    @staticmethod
    def download_file(path1, path2):
        """
        :param path1: server file's path to the file
        :param path2: destination file's path on the local machine
        """
        bytes_count = 0
        start = time.time()
        for data in FTPClient.ftp.download_file(path1):
            bytes_count += len(data)
            try:
                with open(path2, 'ab') as file:
                    file.write(data)
            except:
                FTPClient.eprint(sys.exc_info()[1])
                return

        result_time = time.time() - start
        speed = round(bytes_count / (1024 ** 2) / result_time, 4)
        info_string = '{} bytes received in {} secs ({} MB/s)'.format(bytes_count,
                                                                      round(result_time, 2),
                                                                      speed)
        print(info_string)

    @staticmethod
    def download_directory(current_path, dest_path):
        """
        :param current_path: current server's path
        :param dest_path: current local path
        """
        try:
            files = FTPClient.ftp.list_files(current_path)
        except ftplib.WrongResponse as e:
            FTPClient.eprint(e)
            return
        for t in files:
            name = t[0]
            server_path = '{}/{}'.format(current_path.rstrip('/'), name)
            print(server_path)
            next_path = '{}/{}'.format(dest_path, name)
            if t[1]:
                try:
                    FTPClient.download_file(server_path, next_path)
                except ftplib.WrongResponse as e:
                    FTPClient.eprint(e)
            else:
                os.mkdir(next_path)
                FTPClient.download_directory(server_path, next_path)

    @get_func
    @staticmethod
    def upload_handler(args):
        """
        usage: put <path1> [<path2>]
        Send file which is located in 'path1' to the server's 'path2'
        """
        if not args:
            raise ValueError
        file_name = os.path.split(args[0])[-1]
        path2 = args[1] if len(args) > 1 else './'
        path2 = path2.rstrip('/')
        path2 = os.path.normpath('{}/{}'.format(path2, file_name))
        FTPClient.upload_file(args[0], path2)

    @staticmethod
    def upload_file(path1, path2):
        """
        :param path1: local file's path
        :param path2: remote file's path
        """
        try:
            with open(path1, 'rb') as file:
                data = file.read()
        except:
            FTPClient.eprint(sys.exc_info()[1])
        else:
            FTPClient.ftp.upload_file(path2, data)

    @get_func
    @staticmethod
    def user_handler(args):
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
            FTPClient.ftp.login(username, password)

    @get_func
    @staticmethod
    def pwd_handler(args):
        """
        Print current directory on remote machine
        """
        FTPClient.ftp.get_location()

    @get_func
    @staticmethod
    def remove_handler(args):
        """
        usage: rm [-r] <path>
        Remove file on the remote machine
        optional arguments:
        -r\t\tremove directory
        """
        if not args or (args[0] == '-r' and len(args) == 1):
            raise ValueError
        if args[0] == '-r':
            FTPClient.ftp.remove_directory(args[1])
        else:
            FTPClient.ftp.remove_file(args[0])

    @get_func
    @staticmethod
    def rename_handler(args):
        """
        usage: ren <file name>
        Rename file
        """
        if len(args) != 2:
            raise ValueError
        else:
            FTPClient.ftp.rename_file(args[0], args[1])

    @get_func
    @staticmethod
    def cd_handler(args):
        """
        usage: cd <path>
        Change remote working directory
        """
        if not args:
            raise ValueError
        FTPClient.ftp.change_directory(args[0])

    @get_func
    @staticmethod
    def mkdir_handler(args):
        """
        usage: mkdir <directory name>
        Make directory on the remote machine
        """
        if not args:
            raise ValueError
        FTPClient.ftp.make_directory(args[0])

    @get_func
    @staticmethod
    def ls_handler(args):
        """
        usage: ls [-l] [<path>]
        Show content of remote directory
        opitonal arguments:
        -l\t\tShow content in list
        """
        if args:
            if args[0] == '-l':
                if len(args) > 1:
                    FTPClient.ftp.get_files(args[1])
                else:
                    FTPClient.ftp.get_files()
            else:
                FTPClient.ftp.get_filenames(args[0])
        else:
            FTPClient.ftp.get_filenames()

    @get_func
    @staticmethod
    def size_handler(args):
        """
        usage: size <file_name>
        Show size of remote file
        """
        if not args:
            raise ValueError
        FTPClient.ftp.get_size(args[0])

    @get_func
    @staticmethod
    def debug_handler(args):
        """
        Toggle debugging mode
        """
        if FTPClient.ftp.print_output:
            print('Debug is off')
        else:
            print('Debug is on')
        FTPClient.ftp.print_output = not FTPClient.ftp.print_output

    @get_func
    @staticmethod
    def switch_mode_handler(args):
        """
        Enter passive or active transfer mode
        """
        FTPClient.ftp.passive_state = not FTPClient.ftp.passive_state
        message = 'Passive mode is on' if FTPClient.ftp.passive_state else 'Active mode is on'
        print(message)

    @get_func
    @staticmethod
    def help_handler(args):
        """
        usage: help [<command>]
        Print local help information about command. If command isn't specified show all available commands
        """
        if not args:
            print('Commands: ')
            print('    '.join(filter(None, FTPClient.handlers.keys())))
        else:
            command = args[0]
            if command in FTPClient.handlers:
                for i in filter(None, FTPClient.handlers[command].__doc__.split('\n')):
                    print(i.lstrip())
            else:
                print('Unknown command "{}".'.format(command))

    @get_func
    @staticmethod
    def exit_handler(args):
        """
        Terminate ftp session and exit
        """
        print('Goodbye')
        FTPClient.ftp.close_connection()
        raise SystemExit

    @get_func
    @staticmethod
    def unknown_command_handler(args):
        """
        Handle unknown commands
        """
        print('Unknown command. Use "help"')

    @staticmethod
    def eprint(*args, **kwargs):
        """
        Print message to the sys.stderr
        """
        print(*args, file=sys.stderr, **kwargs)

    @staticmethod
    def validate_path(path):
        """
        Return available directory's path by adding '*' symbol to the end
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
        FTPClient.connect(args)
        FTPClient.cd_handler([FTPClient.current_directory])

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
        'debug': debug_handler,
        'mode': switch_mode_handler,
        'help': help_handler,
        'exit': exit_handler,
        None: unknown_command_handler
    }


if __name__ == '__main__':
    a = Parser.parse_arguments()
    FTPClient.connect(a)
    FTPClient.run()
