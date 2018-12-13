import re
import socket
from typing import Generator, List, Tuple

from .mode import Mode
from .talker import Talker

FILE_REGEX = re.compile(
    (r'^(?P<dir>d?)(?:.+)(?:(?<= \d{4} )|(?<= \d{2}:\d{2} ))'
     r'(?P<filename>.+)$'),
    re.MULTILINE)


class FtpApi:
    def __init__(self, talker: Talker):
        self.talker = talker
        self.talker._get_response()

    def login(self, user: str, password: str):
        self.talker.run_command('USER', user)
        self.talker.run_command('PASS', password)

    def quit(self):
        self.talker.run_command("QUIT")
        self.talker.close_connection()

    def switch_mode(self, mode: Mode):
        self.talker.run_command('TYPE', mode.value[0])

    def get_file(self, path) -> Generator[bytes, None, None]:
        file_size = self.try_get_size(path)
        if file_size == -1:
            file_size = None  # type: ignore

        self.switch_mode(Mode.Binary)
        self.talker._open_data_connection()
        self.talker.run_command('RETR', path)
        yield from self.talker._read_data(file_size, show_progress=True)
        self.talker._get_response()

    def upload_file(self, path: str, data: bytes):
        self.switch_mode(Mode.Binary)
        self.talker._open_data_connection()
        self.talker.run_command('STOR', path)
        self.talker._send_data(data)
        self.talker._get_response()

    def get_current_location(self) -> str:
        return self.talker.run_command('PWD').message

    def remove_file(self, path: str):
        self.talker.run_command('DELE', path)

    def rename_file(self, old_name: str, new_name: str):
        self.talker.run_command('RNFR', old_name)
        self.talker.run_command('RNTO', new_name)

    def try_get_size(self, path: str) -> int:
        self.switch_mode(Mode.Binary)
        result = self.talker.run_command('SIZE', path).message
        self.switch_mode(Mode.Ascii)
        try:
            return int(result)
        except ValueError:
            return -1

    def remove_directory(self, path: str):
        self.talker.run_command('RMD', path)

    def change_directory(self, path: str):
        self.talker.run_command('CWD', path)

    def make_directory(self, path: str):
        self.talker.run_command('MKD', path)

    def list_files_raw(self, path='') -> str:
        self.talker._open_data_connection()
        self.talker.run_command('LIST', path)

        chunks = []
        for chunk in self.talker._read_data():
            chunks.append(chunk.decode(encoding='utf-8', errors='ignore'))
        self.talker._get_response()
        return ''.join(chunks)

    def list_files(self, path='') -> List[Tuple[str, bool]]:
        """Returns list of tuples (<file_name>, <is_file>)
        """
        data = self.list_files_raw(path).replace('\r\n', '\n')

        result = []
        for match in FILE_REGEX.finditer(data):
            is_file = match.group('dir') == ''
            filename = match.group('filename')
            result.append((filename, is_file))

        return result
