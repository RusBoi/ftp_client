import socket
import re
import time
from response import Response
from enum import Enum


BUFFER_SIZE = 1024 * 8  # 8KB
PORT = 60666


class Error(Exception):
    pass


class WrongResponse(Error):
    def __init__(self, response):
        self.response = response


class NoResponse(Error):
    pass


class Color:
    green = '\033[92m'
    red = '\033[91m'
    end_color = '\033[0m'


class DataType(Enum):
    Null = 0,
    Binary = 1,
    ASCII = 2


class FTP:
    def __init__(self, host, port=21):
        self.command_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.command_socket.settimeout(10.0)
        self.command_socket.connect((host, port))
        self.run_command('')

        self.passive_state = True
        self.debug = True
        self.data_type = DataType.Null

    def close_connection(self):
        """
        Close connection with the server
        """
        # self.run_command('QUIT')  # если тайм аут то команду нет сымсла слать
        self.command_socket.close()

    def read_line(self):
        """
        Read bytes from the command socket.
        :return: utf-8 string
        """
        line = b''
        while True:
            byte = self.command_socket.recv(1)
            if byte == b'\n' or byte == b'':
                break
            line += byte
        return line[:-1].decode()

    def get_response(self):
        """
        Try to get response from the server. If there is no response raise NoResponse exception.
        :return: response from the server
        """

        lines = []
        regex = re.compile(r'^(?P<code>\d+?)(?P<delimeter> |-)(?P<message>.+)$')
        while True:
            try:
                line = self.read_line()
            except:
                raise NoResponse
            match = regex.fullmatch(line)
            if match is None:
                lines.append(line)
            else:
                lines.append(match.group('message'))
                if match.group('delimeter') == ' ':
                    return Response(int(match.group('code')), '\n'.join(lines))

    def send_command(self, command, args):
        """
        Send command to the server. Print command to the console if debug flag is on.
        :param command: command which will be sent to the server
        :param args: positional arguments
        """
        if args:
            command_string = '{} {}'.format(command, ' '.join(args))
        else:
            command_string = command
        if self.debug:
            if command == 'PASS':
                print('>>', 'PASS XXXX')
            else:
                print('>>', command_string)
        self.command_socket.sendall((command_string + '\r\n').encode('utf-8'))

    def run_command(self, command, *args):
        """
        Send command to the server and get response. If response is bad than WrongResponse exception
        will be raised. If there is no exception than print the response to the console.
        :param command: command which will be sent to the server
        :param args: positional arguments
        :return: response from the server
        """

        if command:
            self.send_command(command, args)
        result = self.get_response()
        if not result.done:
            raise WrongResponse(result)
        print(Color.green + '<< ' + str(result) + Color.end_color)
        return result

    def open_data_connection(self):
        """
        Open connection to retrieve and send data to the server.
        Connection can be open in two modes: passive and active (depending on "passive_state" flag)
        """

        self.data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.data_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.data_socket.settimeout(10)

        if self.passive_state:
            regex = re.compile(r'\((\d+,\d+,\d+,\d+),(\d+),(\d+)\)')
            func = lambda x: '.' if x == ',' else x
            res = self.run_command('PASV')
            match = regex.search(res.message)
            ip = ''.join(map(func, match.group(1)))
            port = 256 * int(match.group(2)) + int(match.group(3))
            self.data_socket.connect((ip, port))
        else:
            res = self.run_command('PORT', '192,168,1,40,{},{}'.format(PORT // 256, PORT % 256))
            self.data_socket.bind(('', PORT))
            self.data_socket.listen(100)

    def read_data(self):
        """
        Get data from data connection socket
        :return: bytes of data
        """
        data = b''
        if self.passive_state:
            while True:
                try:
                    chunk = self.data_socket.recv(BUFFER_SIZE)
                except:
                    raise NoResponse
                if not chunk:
                    break
                data += chunk
        else:
            conn, addr = self.data_socket.accept()
            while True:
                try:
                    chunk = conn.recv(BUFFER_SIZE)
                except:
                    raise NoResponse
                if not chunk:
                    break
                data += chunk
            conn.close()
        self.data_socket.close()
        return data

    def send_data(self, data):
        """
        Send data via data connection socket
        :param data: data (bytes) to send
        """
        if self.passive_state:
            self.data_socket.send(data)
        else:
            conn, (addr, port) = self.data_socket.accept()
            conn.send(data)
            conn.close()
        self.data_socket.close()

    def download_file(self, file_name):
        """
        Download file from the server
        :param file_name: name of the file
        :return bytes of data
        """

        self.run_command('TYPE', 'I')
        self.open_data_connection()
        resp = self.run_command('RETR', file_name)

        start = time.time()
        data = self.read_data()
        self.run_command('')

        time_value = time.time() - start
        bytes_count = len(data)
        speed = round(bytes_count / (1024 ** 2) / time_value, 4)
        info_string = '{} bytes received in {} secs ({} MB/s)'.format(bytes_count,
                                                                      round(time_value, 2),
                                                                      speed)
        print(info_string)
        return data

    def download_directory(self, directory_name):
        """
        Download recursively whole directory from the server
        :param directory_name: directory's name
        :return: list of tuples containing filename and it's data
        """
        pass

    def upload_file(self, file_name, data):
        """
        Upload a file on the server
        :param file_name: name of the file
        :param data: file's content (bytes)
        """

        self.run_command('TYPE', 'I')
        self.open_data_connection()
        self.run_command('STOR', file_name)
        self.send_data(data)
        self.run_command('')

    def login(self, user, passwd):
        """
        Sign in to the server

        :param user: username
        :param passwd: password
        """
        self.run_command('USER', user)
        self.run_command('PASS', passwd)

    def get_location(self):
        self.run_command('PWD')

    def remove_file(self, path):
        self.run_command('DELE', path)

    def rename_file(self, current_name, name):
        self.run_command('RNFR', current_name)
        self.run_command('RNTO', name)

    def remove_directory(self, path):
        self.run_command('RMD', path)

    def change_directory(self, path):
        self.run_command('CWD', path)

    def make_directory(self, folder_name):
        self.run_command('MKD', folder_name)

    def get_files(self, path=''):
        self.open_data_connection()
        self.run_command('LIST', path)
        data = self.read_data().decode(encoding='utf-8')
        print(data)
        self.run_command('')

    def get_filenames(self, path=''):
        self.open_data_connection()
        self.run_command('NLST', path)
        data = self.read_data().decode(encoding='utf-8')
        print(data)
        self.run_command('')

    def get_size(self, file_name):
        self.run_command('SIZE', file_name)
