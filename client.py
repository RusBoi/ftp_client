import ftplib
import argparse
import help


class FTPClient:
    def __init__(self):
        parser = argparse.ArgumentParser(description="""Ftp client server""")
        parser.add_argument('--host', help='Host to connect to')
        parser.add_argument('--port', '-p', type=int, help='Port to connect to')
        parser.add_argument('--user', '-u', help='Username to login')
        parser.add_argument('--pass', help='Password to login')
        args = parser.parse_args()
        host = input('Enter host name: ') if args.host is None else args.host
        port = int(input('Enter port: ')) if args.port is None else args.port

        try:
            self.ftp = ftplib.FTP(host, port)
        except:
            print('Connection failed.')
            exit(1)

        try:
            self.user_handler([])
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
            'passive': self.switch_mode_handler,
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
            'passive': help.PASSIVE_HELP,
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
                    print('Wrong command')
                else:
                    try:
                        self.handlers[command](args)
                    except ftplib.WrongResponse as e:
                        if e.response.code == 421:
                            print('Timeout')
                            self.exit_handler([])  # Если timeout то соединение восстановить не удастся и поэтому закроем клиент
                        print(ftplib.Color.red + '<< ' + str(e.response) + ftplib.Color.end_color)
                    except ftplib.NoResponse:
                        print(ftplib.Color.red + 'No response. "exit" to quit' + ftplib.Color.end_color)

    def download_handler(self, args):
        for file_name in args:
            data = self.ftp.download_file(file_name).decode(encoding='utf-8')
            with open(file_name, 'w') as file:
                file.write(data)

    def upload_handler(self, args):
        if args:
            for arg in args:
                try:
                    with open(arg) as f:
                        data = f.read()
                except:
                    print("Can't open file")
                else:
                    self.ftp.upload_file(arg, data)
        else:
            print('Wrong arguments')

    def user_handler(self, args):
        username = args[0] if args else input('Enter username: ')
        self.ftp.login(username)

    def pwd_handler(self, args):
        self.ftp.get_location()

    def remove_handler(self, args):
        if args:
            if args[0] == '-r':
                if len(args) > 1:
                    for i in args[1:]:
                        self.ftp.remove_directory(i)
                    else:
                        print('Wrong arguments!')
            else:
                for i in args:
                    self.ftp.remove_file(i)
        else:
            print('Wrong arguments!')

    def rename_handler(self, args):
        if len(args) != 2:
            print('Wrong arguments')
        else:
            self.ftp.rename_file(args[0], args[1])

    def cd_handler(self, args):
        if args:
            self.ftp.change_directory(args[0])
        else:
            print('Wrong arguments!')

    def mkdir_handler(self, args):
        if args:
            for i in args:
                self.ftp.make_directory(i)
        else:
            print('Wrong arguments!')

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
                print('{}\t\t\t{}'.format(command, self.helps[command]))
            else:
                print('Unknown command')

    def exit_handler(self, args):
        self.ftp.close_connection()
        exit(0)


if __name__ == '__main__':
    f = FTPClient()
    f.run()