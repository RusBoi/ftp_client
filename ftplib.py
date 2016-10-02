import socket
import re
import time
from response import Response

BUFFER_SIZE = 1024 ** 3  # 1GB
TIMEOUT = 10.0


class Error(Exception):
    pass


class WrongResponse(Error):
    def __init__(self, response):
        self.response = response


class FTP:
    def __init__(self, host, port, printout=print):
        self.command_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.printout = printout
        self.passive_state = True
        self.debug = False

        self.command_socket.settimeout(TIMEOUT)
        self.command_socket.connect((host, port))
        self.run_command('')

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
        return res[:-1].decode()

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
                self.printout('>>', 'PASS XXXX')
            else:
                self.printout('>>', command_string)
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
        self.printout('<<', result)
        return result

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
            res = self.run_command('PASV')
            match = regex.search(res.message)
            ip = ''.join(map(func, match.group(1)))
            port = 256 * int(match.group(2)) + int(match.group(3))
            self.data_socket.connect((ip, port))
        else:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("google.com", 80))
            func = lambda x: ',' if x == '.' else x
            local_ip = ''.join(map(func, s.getsockname()[0]))
            local_port = int(s.getsockname()[1])

            self.run_command('PORT', '{},{},{}'.format(local_ip, local_port // 256, local_port % 256))
            self.data_socket.bind(('', local_port))
            self.data_socket.listen(100)

    def read_data(self, bytes_count=BUFFER_SIZE, debug=False):
        """
        Get data from data connection socket
        :param bytes_count: if you know how much you need to read from data socket then you can specify it
        :param debug: if file is downloading the info will be printing
        :return: bytes of data
        """
        res = bytearray()
        length = 0
        if self.passive_state:
            while True:
                chunk = self.data_socket.recv(bytes_count)
                length += len(chunk)
                res += chunk
                if not chunk:
                    break
                if debug:
                    pers = round(length / self._size * 100, 2)
                    self.printout('{}%\r'.format(pers), end='')
        else:
            conn = self.data_socket.accept()[0]
            while True:
                chunk = conn.recv(bytes_count)
                length += len(chunk)
                res += chunk
                if not chunk:
                    break
                if debug:
                    pers = round(length / self._size * 100, 2)
                    self.printout('{}%\r'.format(pers), end='')
            conn.close()
        self.data_socket.close()
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

    def download_file(self, file_name):
        """
        Download file from the server
        :param file_name: name of the file
        :return bytes of data
        """
        try:
            resp = self.run_command('SIZE', file_name)
            self._size = int(resp.message)
        except:
            self._size = None

        self.run_command('TYPE', 'I')
        self.open_data_connection()
        self.run_command('RETR', file_name)

        start = time.time()
        if self._size:
            data = self.read_data(debug=True)
        else:
            data = self.read_data(debug=False)
        self.run_command('')

        time_value = time.time() - start
        bytes_count = len(data)
        speed = round(bytes_count / (1024 ** 2) / time_value, 4)
        info_string = '{} bytes received in {} secs ({} MB/s)'.format(bytes_count,
                                                                      round(time_value, 2),
                                                                      speed)
        self.printout(info_string)
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
        self.printout(data)
        self.run_command('')

    def get_filenames(self, path=''):
        self.open_data_connection()
        self.run_command('NLST', path)
        data = self.read_data().decode(encoding='utf-8')
        self.printout(data)
        self.run_command('')

    def get_size(self, file_name):
        self.run_command('SIZE', file_name)
