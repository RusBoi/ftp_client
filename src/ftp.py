import re
import socket

from mode import Mode
from response import Response


BUFFER_SIZE = 1024 ** 2 * 20  # 20MB
TIMEOUT = 60
DATA_SOCK_TIMEOUT = 15


class Error(Exception):
    pass


class WrongResponse(Error):
    def __init__(self, response):
        self.response = response


class FTP:
    def __init__(self, host, port, callback=print,
                 verbose_input=True, verbose_output=False):
        self.command_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.callback = callback
        self.passive_mode = False
        self.verbose_input = verbose_input
        self.verbose_output = verbose_output

        self._resp_regex = re.compile(
            r'^(?P<code>\d+?)(?P<delimeter> |-)(?P<message>.+)$')
        self._files_regex = re.compile(
            (r'^(?P<dir>d?)(?:.+)(?:(?<= \d{4} )|(?<= \d{2}:\d{2} ))'
             r'(?P<filename>.+)$'),
            re.MULTILINE)

        self.command_socket.settimeout(TIMEOUT)
        self.command_socket.connect((host, port))
        self._get_response()

    def _close_connection(self):
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
        return res[:-1].decode(errors='ignore')

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
        self.data_socket.settimeout(DATA_SOCK_TIMEOUT)

        if self.passive_mode:
            regex = re.compile(r'\((\d+,\d+,\d+,\d+),(\d+),(\d+)\)')
            res = self.run_command('PASV')
            match = regex.search(res.message)
            if not match:
                raise WrongResponse(res)
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

    def _read_data(self, data_size=None, buffer_size=BUFFER_SIZE,
                   show_progress=False):
        """Get data from data connection socket. The amount of data can't be
        bigger than MAX_SIZE
        """
        downloaded_size = 0
        if self.passive_mode:
            sock = self.data_socket
        else:
            sock = self.data_socket.accept()[0]
            sock.settimeout(DATA_SOCK_TIMEOUT)

        while True:
            chunk = sock.recv(buffer_size)
            downloaded_size += len(chunk)
            yield chunk
            if show_progress:
                if data_size is None:
                    print(f'{downloaded_size // 1024 >> 10}MB', end='\r')
                else:
                    percents = str(round(downloaded_size / data_size * 100))
                    print(percents + '%', end='\r')
            if chunk == b'':
                break

    def _send_data(self, bytes):
        """Send data via data connection socket
        """
        if self.passive_mode:
            conn = self.data_socket
        else:
            conn, _ = self.data_socket.accept()
        conn.sendall(bytes)
        conn.close()

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

    def login(self, user, password):
        self.run_command('USER', user)
        self.run_command('PASS', password)

    def quit(self):
        self.run_command("QUIT")
        self._close_connection()

    def switch_mode(self, mode: Mode):
        self.run_command('TYPE', mode.value[0])

    def get_file(self, path):
        try:
            resp = self.get_size(path)
            file_size = int(resp)
        except ValueError:
            file_size = None

        self.switch_mode(Mode.Binary)
        self._open_data_connection()
        self.run_command('RETR', path)
        yield from self._read_data(file_size, show_progress=True)
        self._get_response()

    def upload_file(self, path, data):
        self.switch_mode(Mode.Binary)
        self._open_data_connection()
        self.run_command('STOR', path)
        self._send_data(data)
        self._get_response()

    def get_current_location(self):
        return self.run_command('PWD').message

    def remove_file(self, path):
        self.run_command('DELE', path)

    def rename_file(self, old_name, new_name):
        self.run_command('RNFR', old_name)
        self.run_command('RNTO', new_name)

    def get_size(self, path):
        self.switch_mode(Mode.Binary)
        result = self.run_command('SIZE', path).message
        self.switch_mode(Mode.Ascii)
        return result

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
            chunks.append(chunk.decode(encoding='utf-8', errors='ignore'))
        self._get_response()
        return ''.join(chunks)

    def list_files(self, path=''):
        """Returns list of tuples (<file_name>, <is_file>)
        """
        data = self._list_files(path).replace('\r\n', '\n')

        result = []
        for match in self._files_regex.finditer(data):
            is_file = match.group('dir') == ''
            filename = match.group('filename')
            result.append((filename, is_file))

        return result
