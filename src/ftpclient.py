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


class FtpClient:
    def __init__(self, host, port, printout=print, print_input=True,
                 print_output=False):
        self.command_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.printout = printout
        self.passive_state = True
        self.print_input = print_input
        self.print_output = print_output

        self._size = None
        self._current_size = None
        self._resp_regex = re.compile(
            r'^(?P<code>\d+?)(?P<delimeter> |-)(?P<message>.+)$')

        self.command_socket.settimeout(TIMEOUT)
        self.command_socket.connect((host, port))
        self.run_command('')

    def close_connection(self):
        """Close connection with the server
        """
        self.command_socket.close()

    def _read_line(self):
        """Read from the command socket
        """
        res = bytearray()
        while True:
            byte = self.command_socket.recv(1)
            if byte in (b'\n', b''):
                break
            res += byte
        return res[:-1].decode(errors='skip')

    def _get_response(self):
        """Get response from the server.
        """
        lines = []
        while True:
            line = self._read_line()
            match = self._resp_regex.fullmatch(line)
            if match is None:
                lines.append(line)
            else:
                lines.append(match.group('message'))
                if match.group('delimeter') == ' ':
                    return Response(int(match.group('code')), '\n'.join(lines))

    def _send_message(self, message):
        """Send message to the server.
        """
        self.command_socket.sendall((message + '\r\n').encode('utf-8'))

    def run_command(self, command, *args, printin=None, printout=None):
        """Send command to the server and get response. If response is bad than
        WrongResponse exception is raised. If there is no exception than print
        the response to the console.
        :param command: command which will be sent to the server
        :param args: positional arguments
        :param printin: print incoming messages
        :param printout: print outcoming messages
        :return: response from the server
        """
        message = command
        if len(args) != 0:
            message += ' ' + ' '.join(args)

        if printin is None:
            printin = self.print_input
        if printout is None:
            printout = self.print_output

        if message is not None:
            self._send_message(message)
            if printout:
                if command == 'PASS':
                    self.printout('>>', 'PASS XXXX')
                else:
                    self.printout('>>', message)

        result = self._get_response()
        if not result.done:
            raise WrongResponse(result)
        if printin:
            self.printout('<<', result)
        return result

    def open_data_connection(self):
        """
        Open connection to retrieve and send data to the server.
        Connection can be open in two modes: passive and active
        (depending on "passive_state" flag)
        """
        self.data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.data_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.data_socket.settimeout(TIMEOUT)

        if self.passive_state:
            regex = re.compile(r'\((\d+,\d+,\d+,\d+),(\d+),(\d+)\)')
            func = lambda x: '.' if x == ',' else x
            res = self.run_command('PASV')
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

            self.run_command(
                'PORT',
                f'{local_ip},{local_port // 256},{local_port % 256}')
            self.data_socket.bind(('', local_port))
            self.data_socket.listen(100)

    def read_data(self, buffer_size=BUFFER_SIZE, debug=False):
        """
        Get data from data connection socket. The amount of data can't be
        bigger than MAX_SIZE
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

    def send_data(self, bytes):
        """Send data via data connection socket
        """
        if self.passive_state:
            self.data_socket.sendall(bytes)
        else:
            conn, _ = self.data_socket.accept()
            conn.sendall(bytes)
            conn.close()
        self.data_socket.close()

    def download_file(self, path):
        """Download file from the server
        """
        try:
            resp = self.run_command('SIZE', path)
            self._size = int(resp.message)
        except:
            self._size = None
        self._current_size = 0

        self.run_command('TYPE', 'I')
        self.open_data_connection()
        self.run_command('RETR', path)

        while True:
            if self._size:
                data = self.read_data(debug=True)
            else:
                data = self.read_data(debug=False)
            if len(data) == 0:
                self.data_socket.close()
                self.run_command('')
                break
            else:
                yield data

    def upload_file(self, path, data):
        """Upload a file on the server
        """
        self.run_command('TYPE', 'I')
        self.open_data_connection()
        self.run_command('STOR', path)
        self.send_data(data)
        self.run_command('')

    def login(self, user, passwd):
        """Sign in to the server
        """
        self.run_command('USER', user)
        self.run_command('PASS', passwd)

    def get_location(self):
        """Get current user location on the server
        """
        self.run_command('PWD')

    def remove_file(self, path):
        """Remove file from the server
        """
        self.run_command('DELE', path)

    def rename_file(self, old_name, new_name):
        """Rename file
        """
        self.run_command('RNFR', old_name)
        self.run_command('RNTO', new_name)

    def remove_directory(self, path):
        """Remove directory on the server
        """
        self.run_command('RMD', path)

    def change_directory(self, path):
        """Change current user directory
        """
        self.run_command('CWD', path)

    def make_directory(self, path):
        """Make directory on the server
        """
        self.run_command('MKD', path)

    def list_files(self, path=''):
        """Get content of the directory.
        Returns: list of tuples (<file_name>, <is_file>)
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
        """Get content of the directory
        """
        self.open_data_connection()
        self.run_command('LIST', path)
        data = self.read_data().decode(encoding='utf-8', errors='skip')
        self.printout(data)
        self.run_command('')

    def get_filenames(self, path=''):
        """Get content of the directory in simplified way
        """
        files = self.list_files(path)
        for t in files:
            self.printout(t[0], 'file' if t[1] else 'directory', sep='     ')

    def get_size(self, path):
        """Get size of the file
        """
        self.run_command('SIZE', path)
