import unittest
from time import sleep
from unittest.mock import Mock, patch

from src.ftp import FTP, WrongResponse
from src.response import Response


def list_of_bytes(s):
    return list(map(lambda i: i.encode(), s))


class FTPTests(unittest.TestCase):
    def setUp(self):
        self.connect_patcher = patch('socket.socket.connect',
                                     return_value=None)
        self.message_patcher = patch.object(FTP, '_send_message',
                                            return_value=None)
        self.resp_patcher = patch.object(FTP, '_get_response')

        self.connect_patcher.start()
        self.message_patcher.start()

        self.resp_mock = self.resp_patcher.start()
        self.resp_mock.return_value = Response(200, 'Welcome')
        self.ftp = FTP('valid-host', 21)

    def tearDown(self):
        self.connect_patcher.stop()
        self.message_patcher.stop()
        self.resp_patcher.stop()

    def test_ftp_object_creation(self):
        self.assertIsNotNone(self.ftp)

    def test_login_with_invalid_credentials(self):
        responses = [
            Response(331, 'Password required'),
            Response(530, 'Login incorrect')
        ]
        self.resp_mock.side_effect = responses

        with self.assertRaises(WrongResponse):
            self.ftp.login('invalid_user', 'invalid_pass')

    def test_anonymous_login(self):
        responses = [
            Response(331, 'Password required'),
            Response(230, 'Login successful')
        ]
        self.resp_mock.side_effect = responses

        self.ftp.login('anonymous', '123')

    def test_size(self):
        responses = [
            Response(200, 'Mode was switched to binary'),
            Response(200, '100 bytes'),
            Response(200, 'Mode was switched to ascii'),
        ]
        self.resp_mock.side_effect = responses

        actual = self.ftp.get_size('file.txt')
        self.assertEqual(actual, '100 bytes')

    def test_list_files(self):
        listing = """-rw-rw-r--   1 ftp      ftp       9967461 08:00 01-Globus.mp3\r\n
-rw-rw-r--   1 ftp      ftp       5525649 Dec 10  2007 02   Gospoda demokraty.mp3\r\n
drw-rw-r--   1 ftp      ftp       8650309 Dec 11  2007 03 Byvshiy podjesaul.mp3\r\n
-rw-rw-r--   1 ftp      ftp      12458333 15:32 07-Letniy dozhd.mp3\r\n
drw-rw-r--   1 ftp      ftp       8245331 Dec 11  2007 11-Byvshiy podjesaul (1-y variant fonogrammy).mp3\r\n
        """

        with patch.object(FTP, '_list_files', return_value=listing):
            expected = [
                ('01-Globus.mp3', True),
                ('02   Gospoda demokraty.mp3', True),
                ('03 Byvshiy podjesaul.mp3', False),
                ('07-Letniy dozhd.mp3', True),
                ('11-Byvshiy podjesaul (1-y variant fonogrammy).mp3', False),
            ]

            self.assertEqual(self.ftp.list_files(), expected)

    def test_file_downloading(self):
        file_size = 100000
        responses = [
            Response(200, 'Type set to I'),
            Response(213, str(file_size)),
            Response(200, 'Type set to A'),
            Response(200, 'Type set to I'),
            Response(150, 'Opening BINARY mode data connection for file')
        ]
        self.resp_mock.side_effect = responses

        with patch.object(self.ftp, '_open_data_connection', return_value=None):
            data_mock = Mock()
            mock = Mock()
            data_mock.accept.return_value = (mock,)
            mock.recv.side_effect = (b'#' for i in range(file_size))
            self.ftp.data_socket = data_mock

            actual = b''.join(self.ftp.get_file('test-file.txt'))
            self.assertEqual(actual, b'#' * file_size)

    def return_byte_with_delay(self, file_size, delay):
        for i in range(file_size):
            sleep(delay)
            yield b'#'

    def test_slow_file_downloading(self):
        file_size = 3
        responses = [
            Response(200, 'Type set to I'),
            Response(213, str(file_size)),
            Response(200, 'Type set to A'),
            Response(200, 'Type set to I'),
            Response(150, 'Opening BINARY mode data connection for file')
        ]
        self.resp_mock.side_effect = responses

        with patch.object(self.ftp, '_open_data_connection', return_value=None):
            data_mock = Mock()
            mock = Mock()
            data_mock.accept.return_value = (mock,)
            mock.recv.side_effect = self.return_byte_with_delay(file_size, 5)
            self.ftp.data_socket = data_mock

            actual = b''.join(self.ftp.get_file('test-file.txt'))
            self.assertEqual(actual, b'#' * file_size)
