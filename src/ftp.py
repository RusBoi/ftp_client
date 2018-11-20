import json
import re
import socket

from mode import Mode
from response import Response


BUFFER_SIZE = 1024 ** 2 * 20  # 20MB
MAX_SIZE = (1024 ** 3)  # 1GB


with open('config.json') as f:
    config = json.load(f)


class Error(Exception):
    pass


class WrongResponse(Error):
    def __init__(self, response):
        self.response = response


class FTP:
    def __init__(self, host, port=config['DEFAULT_PORT'],
                 callback=print, verbose_input=True, verbose_output=False):
        self.command_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.callback = callback
        self.passive_mode = True
        self.verbose_input = verbose_input
        self.verbose_output = verbose_output

        self._resp_regex = re.compile(
            r'^(?P<code>\d+?)(?P<delimeter> |-)(?P<message>.+)$')

        self.command_socket.settimeout(config['TIMEOUT'])
        self.command_socket.connect((host, port))
        self._get_response()

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

    def _open_data_connection(self):
        """Open connection to retrieve and send data to the server.
        Connection can be open in two modes: passive and active
        (depending on "passive_mode" flag)
        """
        self.data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.data_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.data_socket.settimeout(config['TIMEOUT'])

        if self.passive_mode:
            regex = re.compile(r'\((\d+,\d+,\d+,\d+),(\d+),(\d+)\)')
            res = self.run_command('PASV')
            match = regex.search(res.message)
            if not match:
                raise WrongResponse
            ip = ''.join(map(lambda x: '.' if x == ',' else x, match.group(1)))
            port = 256 * int(match.group(2)) + int(match.group(3))
            self.data_socket.connect((ip, port))
        else:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("google.com", 80))
            local_ip = ''.join(map(
                lambda x: ',' if x == '.' else x,
                s.getsockname()[0]))
            local_port = int(s.getsockname()[1])

            self.run_command(
                'PORT',
                f'{local_ip},{local_port // 256},{local_port % 256}')
            self.data_socket.bind(('', local_port))
            self.data_socket.listen(100)

    def _read_data(self, data_size=None, buffer_size=BUFFER_SIZE):
        """Get data from data connection socket. The amount of data can't be
        bigger than MAX_SIZE
        """
        downloaded_size = 0
        if self.passive_mode:
            sock = self.data_socket
        else:
            sock = self.data_socket.accept()[0]
            sock.settimeout(config['TIMEOUT'])

        while True:
            chunk = sock.recv(buffer_size)
            downloaded_size += len(chunk)
            yield chunk
            if chunk == b'':  # or downloaded_size >= data_size:
                break

    def _send_data(self, bytes):
        """Send data via data connection socket
        """
        if self.passive_mode:
            self.data_socket.sendall(bytes)
        else:
            conn, _ = self.data_socket.accept()
            conn.sendall(bytes)
            conn.close()
        self.data_socket.close()

    def run_command(self, command, *args, printin=None, printout=None):
        """Send command to the server and get response. If response is bad than
        WrongResponse exception is raised. If there is no exception than print
        the response to the console.
        """
        message = command
        if len(args) != 0:
            message += ' ' + ' '.join(args)

        if printin is None:
            printin = self.verbose_input
        if printout is None:
            printout = self.verbose_output

        if message is not None:
            self._send_message(message)
            if printout:
                if command == 'PASS':
                    self.callback('>> PASS XXXX')
                else:
                    self.callback(f'>> {message}')

        result = self._get_response()
        if not result.success:
            raise WrongResponse(result)
        if printin:
            self.callback(f'<< {result}')
        return result

    def login(self, user=config['DEFAULT_USERNAME'],
              password=config['DEFAULT_PASS']):
        self.run_command('USER', user)
        self.run_command('PASS', password)

    def quit(self):
        self.run_command("QUIT")

    def switch_mode(self, mode: Mode):
        self.run_command('TYPE', mode.value[0])

    def get_file(self, path):
        try:
            resp = self.run_command('SIZE', path)
            file_size = int(resp.message)
        except:
            file_size = None

        self.switch_mode(Mode.Binary)
        self._open_data_connection()
        self.run_command('RETR', path)
        yield from self._read_data()
        self._get_response()

    def upload_file(self, path, data):
        self.switch_mode(Mode.Binary)
        self._open_data_connection()
        self.run_command('STOR', path)
        self._send_data(data)
        self.run_command('')

    def current_location(self):
        self.run_command('PWD')

    def remove_file(self, path):
        self.run_command('DELE', path)

    def rename_file(self, old_name, new_name):
        self.run_command('RNFR', old_name)
        self.run_command('RNTO', new_name)

    def get_size(self, path):
        self.run_command('SIZE', path)

    def remove_directory(self, path):
        self.run_command('RMD', path)

    def change_directory(self, path):
        self.run_command('CWD', path)

    def make_directory(self, path):
        self.run_command('MKD', path)

    def _list_files(self, path=''):
        self._open_data_connection()
        self.run_command('LIST', path)

        chunks = []
        for chunk in self._read_data():
            chunks.append(chunk.decode(encoding='utf-8', errors='skip'))
        self._get_response()
        return ''.join(chunks)

    def list_files(self, path=''):
        """Returns list of tuples (<file_name>, <is_file>)
        """
        data = self._list_files()

        result = []
        for line in filter(None, data.split('\r\n')):
            result.append((line.split()[-1], line[0] == '-'))
        return result

# if print_state:
#     length += len(chunk)
#     self._current_size += len(chunk)
#     pers = round(self._current_size / self._size * 100, 2)
#     self.callback('{}%\r'.format(pers), end='')
