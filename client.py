
import ftplib
import argparse
import help
import getpass
try:
    import readline
except:
    pass


class FTPClient:
    def __init__(self):
        parser = argparse.ArgumentParser(description="""Ftp client server""")
        parser.add_argument('--host', help='Host to connect to')
        parser.add_argument('--port', '-p', type=int, help='Port to connect to')
        parser.add_argument('--user', '-u', help='Username to login')
        parser.add_argument('--passwd', help='Password to login')
        args = parser.parse_args()
        host = input('Enter host name: ') if args.host is None else args.host
        port = int(input('Enter port: ')) if args.port is None else args.port

        try:
            self.ftp = ftplib.FTP(host, port)
        except:
            print('Connection failed.')
            exit(1)

        user = input('Enter username: ') if args.user is None else args.user
        password = getpass.getpass('Enter password: ') if args.passwd is None else args.passwd

        try:
            self.user_handler([user, password])
        except ftplib.WrongResponse as e:
            if e.response.code == 421:
                print('Timeout')
                self.exit_handler([])  # Если timeout то соединение восстановить не удастся и поэтому закроем клиент
            print(ftplib.Color.red + '<< ' + str(e.response) + ftplib.Color.end_color)
        except:
            pass

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

        self.helps = {
            'get': help.GET_HELP,
            'put': help.PUT_HELP,
            'user': help.USER_HELP,
            'pwd': help.PWD_HELP,
            'rm': help.RM_HELP,
            'ren': help.REN_HELP,
            'cd': help.CD_HELP,
            'mkdir': help.MKDIR_HELP,
            'ls': help.LS_HELP,
            'size': help.SIZE_HELP,
            'debug': help.DEBUG_HELP,
            'mode': help.MODE_HELP,
            'help': help.HELP_HELP,
            'exit': help.EXIT_HELP
        }

    def run(self):
        """
        Главный цикл
        """
        while True:
            try:
                command, *args = input().split(' ')
            except KeyboardInterrupt:
                self.exit_handler([])
            else:
                if command not in self.handlers:
                    print('Unknown command. Use "help"')
                else:
                    try:
                        self.handlers[command](args)
                    except ftplib.WrongResponse as e:
                        if e.response.code == 421:
                            # Если timeout то соединение восстановить не удастся и поэтому закроем клиент
                            print('Timeout')
                            self.exit_handler([])
                        print(ftplib.Color.red + '<< ' + str(e.response) + ftplib.Color.end_color)
                    except ftplib.NoResponse:
                        print(ftplib.Color.red + 'No response. "exit" to quit' + ftplib.Color.end_color)
                    except ConnectionRefusedError as e:
                        print(e)
                    except ValueError:
                        print('Wrong arguments. Use "help <command>"')

    def download_handler(self, args):
        if not args or (args[0] == '-r' and len(args) == 1):
            raise ValueError
        if args[0] == '-r':
            self.download_directory(args[1])
        else:
            self.download_file(args[0])

    # Не доделано
    def download_directory(self, directory_name):
        return
        # all_data = self.ftp.download_directory(directory_name)
        # # Папка может быть пустой
        # for data in all_data:
        #     with open(data[0], 'wb') as file:
        #         file.write(data)

    def download_file(self, file_name):
        data = self.ftp.download_file(file_name)
        with open(file_name, 'wb') as file:
            file.write(data)

    def upload_handler(self, args):
        if not args or (args[0] == '-r' and len(args) == 1):
            raise ValueError
        if args[0] == '-r':
            self.upload_directory(args[1])
        else:
            self.upload_file(args[0])

    # Не доделано
    def upload_directory(self, directory_name):
        pass

    def upload_file(self, file_name):
        try:
            with open(file_name, 'rb') as file:
                data = file.read()
        except:
            print("Can't open file")
        else:
            self.ftp.upload_file(file_name, data)

    def user_handler(self, args):
        username = args[0] if args else input('Enter username: ')
        password = args[1] if len(args) > 1 else getpass.getpass('Enter password: ')
        self.ftp.login(username, password)

    def pwd_handler(self, args):
        self.ftp.get_location()

    def remove_handler(self, args):
        if not args or (args[0] == '-r' and len(args) == 1):
            raise ValueError
        if args[0] == '-r':
            self.ftp.remove_directory(args[1])
        else:
            self.ftp.remove_file(args[0])

    def rename_handler(self, args):
        if len(args) != 2:
            raise ValueError
        else:
            self.ftp.rename_file(args[0], args[1])

    def cd_handler(self, args):
        if not args:
            raise ValueError
        self.ftp.change_directory(args[0])

    def mkdir_handler(self, args):
        if not args:
            raise ValueError
        self.ftp.make_directory(args[0])

    def ls_handler(self, args):
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
        if not args:
            raise ValueError
        self.ftp.get_size(args[0])

    def debug_handler(self, args):
        if self.ftp.debug:
            print('Debug is off')
        else:
            print('Debug is on')
        self.ftp.debug = not self.ftp.debug

    def switch_mode_handler(self, args):
        self.ftp.passive_state = not self.ftp.passive_state
        message = 'Passive mode is on' if self.ftp.passive_state else 'Active mode is on'
        print(message)

    def help_handler(self, args):
        if not args:
            print('Commands: ')
            print('    '.join(self.helps.keys()))
        else:
            command = args[0]
            if command in self.helps:
                print(self.helps[command])
            else:
                print('Unknown command "{}"'.format(command))

    def exit_handler(self, args):
        self.ftp.close_connection()
        exit(0)


if __name__ == '__main__':
    f = FTPClient()
    f.run()