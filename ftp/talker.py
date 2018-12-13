import re
import socket
from typing import Generator

from .errors import WrongResponse
from .response import Response

BUFFER_SIZE = 1024 ** 2 * 20  # 20MB
TIMEOUT = 60
DATA_SOCK_TIMEOUT = 15
RESP_REGEX = re.compile(r'^(?P<code>\d+?)(?P<delimeter> |-)(?P<message>.+)$')


class Talker:
    def __init__(self, host, port, callback=print, verbose_input=True,
                 verbose_output=False):
        self.passive_mode = False  # type: bool

        self.callback = callback
        self.verbose_input = verbose_input
        self.verbose_output = verbose_output

        self._command_socket = socket.socket(socket.AF_INET,
                                             socket.SOCK_STREAM)
        self._command_socket.settimeout(TIMEOUT)
        self._command_socket.connect((host, port))

    def close_connection(self):
        self._command_socket.close()

    def _read_line(self) -> str:
        """Read from the command socket
        """
        res = bytearray()
        while True:
            byte = self._command_socket.recv(1)
            if byte in (b'\n', b''):
                break
            res += byte
        return res[:-1].decode(errors='ignore')

    def _get_response(self) -> Response:
        """Get response from the server.
        """
        lines = []
        while True:
            line = self._read_line()
            match = RESP_REGEX.fullmatch(line)
            if match is None:
                lines.append(line)
            else:
                lines.append(match.group('message'))
                if match.group('delimeter') == ' ':
                    return Response(int(match.group('code')), '\n'.join(lines))

    def _send_message(self, message: str):
        """Send message to the server.
        """
        self._command_socket.sendall((message + '\r\n').encode('utf-8'))

    def _open_data_connection(self):
        """Open connection to retrieve and send data to the server.
        Connection can be open in two modes: passive and active
        (depending on "passive_mode" flag)
        """
        self._data_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._data_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._data_socket.settimeout(DATA_SOCK_TIMEOUT)

        if self.passive_mode:
            regex = re.compile(r'\((\d+,\d+,\d+,\d+),(\d+),(\d+)\)')
            res = self.run_command('PASV')
            match = regex.search(res.message)
            if not match:
                raise WrongResponse(res)
            ip = ''.join(map(lambda x: '.' if x == ',' else x, match.group(1)))
            port = 256 * int(match.group(2)) + int(match.group(3))
            self._data_socket.connect((ip, port))
        else:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("google.com", 80))
            local_ip = ''.join(map(
                lambda x: ',' if x == '.' else x,
                s.getsockname()[0]))
            local_port = int(s.getsockname()[1])

            self.run_command(
                'PORT',
                '{},{},{}'.format(
                    local_ip, local_port // 256, local_port % 256))
            self._data_socket.bind(('', local_port))
            self._data_socket.listen(100)

    def _read_data(self, data_size=None, buffer_size=BUFFER_SIZE,
                   show_progress=False) -> Generator[bytes, None, None]:
        """Get data from data connection socket. The amount of data can't be
        bigger than MAX_SIZE
        """
        downloaded_size = 0
        if self.passive_mode:
            sock = self._data_socket
        else:
            sock = self._data_socket.accept()[0]
            sock.settimeout(DATA_SOCK_TIMEOUT)

        while True:
            chunk = sock.recv(buffer_size)
            downloaded_size += len(chunk)
            yield chunk
            if show_progress:
                if data_size is None:
                    print('{}MB'.format(downloaded_size // 1024 >> 10),
                          end='\r')
                else:
                    percents = str(round(downloaded_size / data_size * 100))
                    print(percents + '%', end='\r')
            if chunk == b'':
                break

    def _send_data(self, data: bytes):
        """Send data via data connection socket
        """
        if self.passive_mode:
            conn = self._data_socket
        else:
            conn, _ = self._data_socket.accept()
        conn.sendall(data)
        conn.close()

    def run_command(self, command: str, *args, printin=None,
                    printout=None) -> Response:
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
                    self.callback('>> {}'.format(message))

        result = self._get_response()
        if not result.success:
            raise WrongResponse(result)
        if printin:
            self.callback('<< {}'.format(result))
        return result
