import re
import socket
from response import Response


BUFFER_SIZE = 1024 ** 2 * 20  # 20MB
MAX_SIZE = (1024 ** 3)  # 1GB
TIMEOUT = 60.0


class Error(Exception):
    pass


class WrongResponse(Error):
    def __init__(self, response):
        self.response = response


class FTP:
    def __init__(self, host, port, printout=print, print_input=True, print_output=False):
        self.command_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.printout = printout
        self.passive_state = True
        self.print_output = print_output
        self.print_input = print_input

        self._size = None
        self._current_size = None

        self.command_socket.settimeout(TIMEOUT)
        self.command_socket.connect((host, port))
        self.run_normal_command('')

    def close_connection(self):
        """
        Close connection with the server
        """
        self.command_socket.close()

    def read_line(self):
        """
        Read bytes from the command socket.
        :return: utf-8 string
        """
        res = bytearray()
        while True:
            byte = self.command_socket.recv(1)
            if byte in (b'\n', b''):
                break
            res += byte
        return res[:-1].decode(errors='skip')

    def get_response(self):
        """
        Try to get response from the server.
        :return: response from the server
        """
        lines = []
        regex = re.compile(r'^(?P<code>\d+?)(?P<delimeter> |-)(?P<message>.+)$')
        while True:
            line = self.read_line()
            match = regex.fullmatch(line)
            if match is None:
                lines.append(line)
            else:
                lines.append(match.group('message'))
                if match.group('delimeter') == ' ':
                    return Response(int(match.group('code')), '\n'.join(lines))

    def send_message(self, message):
        """
        Send message to the server.
        :param message: message which will be sent to the server
        """
        self.command_socket.sendall((message + '\r\n').encode('utf-8'))

    def run_command(self, command, *args, printin=True, printout=True):
        """
        Send command to the server and get response. If response is bad than WrongResponse exception
        will be raised. If there is no exception than print the response to the console.
        :param command: command which will be sent to the server
        :param args: positional arguments
        :param printin: print incoming messages
        :param printout: print outcoming messages
        :return: response from the server
        """
        if args:
            message = '{} {}'.format(command, ' '.join(args))
        else:
            message = command

        if message:
            self.send_message(message)
            if printout:
                if command == 'PASS':
                    self.printout('>>', 'PASS XXXX')
                else:
                    self.printout('>>', message)

        result = self.get_response()
        if not result.done:
            raise WrongResponse(result)
        if printin:
            self.printout('<<', result)
        return result

    def run_normal_command(self, command, *args):
        """
        Running command considering print_input and print_output flags
        :param command: command to send
        :param args: positional arguments
        :return:response from the server
        """
        return self.run_command(command, *args, printin=self.print_input, printout=self.print_output)

    def open_data_connection(self):
        """
        Open connection to retrieve and send data to the server.
        Connection can be open in two modes: passive and active (depending on "passive_state" flag)
        """
        self.data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.data_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.data_socket.settimeout(TIMEOUT)

        if self.passive_state:
            regex = re.compile(r'\((\d+,\d+,\d+,\d+),(\d+),(\d+)\)')
            func = lambda x: '.' if x == ',' else x
            res = self.run_normal_command('PASV')
            match = regex.search(res.message)
            if not match:
                raise WrongResponse
            ip = ''.join(map(func, match.group(1)))
            port = 256 * int(match.group(2)) + int(match.group(3))
            self.data_socket.connect((ip, port))
        else:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("google.com", 80))
            func = lambda x: ',' if x == '.' else x
            local_ip = ''.join(map(func, s.getsockname()[0]))
            local_port = int(s.getsockname()[1])

            self.run_normal_command('PORT', '{},{},{}'.format(local_ip, local_port // 256, local_port % 256))
            self.data_socket.bind(('', local_port))
            self.data_socket.listen(100)

    def read_data(self, buffer_size=BUFFER_SIZE, debug=False):
        """
        Get data from data connection socket. The amount of data can't be bigger than MAX_SIZE
        :param buffer_size: bytes to read in one iteration
        :param debug: if file is downloading the info will be printing
        :return: bytes of data
        """
        res = bytearray()
        length = 0
        if self.passive_state:
            while True:
                chunk = self.data_socket.recv(buffer_size)
                res += chunk
                if not chunk or length >= MAX_SIZE:
                    break
                if debug:
                    length += len(chunk)
                    self._current_size += len(chunk)
                    pers = round(self._current_size / self._size * 100, 2)
                    self.printout('{}%\r'.format(pers), end='')
        else:
            conn = self.data_socket.accept()[0]
            while True:
                chunk = conn.recv(buffer_size)
                res += chunk
                if not chunk or length >= MAX_SIZE:
                    break
                if debug:
                    length += len(chunk)
                    self._current_size += len(chunk)
                    pers = round(self._current_size / self._size * 100, 2)
                    self.printout('{}%\r'.format(pers), end='')
            conn.close()
        return res

    def send_data(self, data):
        """
        Send data via data connection socket
        :param data: data (bytes) to send
        """
        if self.passive_state:
            self.data_socket.sendall(data)
        else:
            conn, (addr, port) = self.data_socket.accept()
            conn.sendall(data)
            conn.close()
        self.data_socket.close()

    def download_file(self, file_path):
        """
        Generator function which downloads file from the server
        :param file_path: name of the file
        :return bytes of data
        """
        try:
            resp = self.run_normal_command('SIZE', file_path)
            self._size = int(resp.message)
        except:
            self._size = None
        self._current_size = 0

        self.run_normal_command('TYPE', 'I')
        self.open_data_connection()
        self.run_normal_command('RETR', file_path)

        while True:
            if self._size:
                data = self.read_data(debug=True)
            else:
                data = self.read_data(debug=False)
            if len(data) == 0:
                self.data_socket.close()
                self.run_normal_command('')
                break
            else:
                yield data

    def upload_file(self, file_path, data):
        """
        Upload a file on the server
        :param file_path: name of the file
        :param data: file's content (bytes)
        """
        self.run_normal_command('TYPE', 'I')
        self.open_data_connection()
        self.run_normal_command('STOR', file_path)
        self.send_data(data)
        self.run_normal_command('')

    def login(self, user, passwd):
        """
        Sign in to the server
        :param user: username
        :param passwd: password
        """
        self.run_normal_command('USER', user)
        self.run_normal_command('PASS', passwd)

    def get_location(self):
        """
        Get current user location on the server
        """
        self.run_normal_command('PWD')

    def remove_file(self, path):
        """
        Remove file from the server
        :param path:
        :return:
        """
        self.run_normal_command('DELE', path)

    def rename_file(self, current_name, name):
        """
        Rename file
        :param current_name: current file's name
        :param name: next file's name
        """
        self.run_normal_command('RNFR', current_name)
        self.run_normal_command('RNTO', name)

    def remove_directory(self, path):
        """
        Remove directory on the server
        :param path: directory's path
        """
        self.run_normal_command('RMD', path)

    def change_directory(self, path):
        """
        Change current user directory
        :param path: directory's path
        """
        self.run_normal_command('CWD', path)

    def make_directory(self, path):
        """
        Make directory on the server
        :param path: directory's path
        """
        self.run_normal_command('MKD', path)

    def list_files(self, path=''):
        """
        Get content of the directory. No output!
        :param path: directory's path
        :return: list of tuples (<file_name>(<dir_name>), <is_it_file>)
        """
        old_in, old_out = self.print_input, self.print_output
        self.print_input, self.print_output = False, False
        self.open_data_connection()
        self.print_input, self.print_output = old_in, old_out

        self.run_command('LIST', path, printin=False, printout=False)
        data = self.read_data().decode(encoding='utf-8', errors='skip')
        self.run_command('', printin=False, printout=False)

        res = []
        for line in filter(None, data.split('\r\n')):
            res.append((line.split()[-1], line[0] == '-'))

        return res

    def get_files(self, path=''):
        """
        Get content of the directory
        :param path: directory's path
        """
        self.open_data_connection()
        self.run_normal_command('LIST', path)
        data = self.read_data().decode(encoding='utf-8', errors='skip')
        self.printout(data)
        self.run_normal_command('')

    def get_filenames(self, path=''):
        """
        Get content of the directory in simplified way
        :param path: directory's path
        """
        files = self.list_files(path)
        for t in files:
            self.printout(t[0], 'file' if t[1] else 'directory', sep='     ')

    def get_size(self, path):
        """
        Get size of the file
        :param path: file's path
        :return:
        """
        self.run_normal_command('SIZE', path)