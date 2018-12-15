import unittest
from time import sleep
from unittest import mock

from ftp.errors import WrongResponse
from ftp.ftp_api import FtpApi
from ftp.response import Response
from ftp.talker import Talker


def list_of_bytes(s):
    return list(map(lambda i: i.encode(), s))


class FtpTest(unittest.TestCase):
    def setUp(self):
        self.response_patch = mock.patch.object(Talker, '_get_response')
        self.socket_patch = mock.patch('ftp.talker.socket.socket',
                                       autospec=True)

        self.response_mock = self.response_patch.start()
        self.socket_mock = self.socket_patch.start()()

        self.socket_mock.connect.return_value = None
        self.socket_mock.bind.return_value = None
        self.socket_mock.listen.return_value = None
        self.socket_mock.accept.return_value = (self.socket_mock, )

        self.api = FtpApi(Talker(None, None))

    def tearDown(self):
        self.response_patch.stop()
        self.socket_patch.stop()

    def test_anonymous_login(self):
        responses = [
            Response(331, 'Password required'),
            Response(230, 'Login successful')]
        self.response_mock.side_effect = responses

        self.api.login('anonymous', 'pass')

    def test_login_with_invalid_credentials(self):
        responses = [
            Response(331, 'Password required'),
            Response(530, 'Login incorrect')]
        self.response_mock.side_effect = responses

        with self.assertRaises(WrongResponse):
            self.api.login('hello', 'invalid_pass')

    def test_getting_valid_size(self):
        responses = [
            Response(200, 'Mode was switched to binary'),
            Response(200, '76861'),
            Response(200, 'Mode was switched to ascii')]
        self.response_mock.side_effect = responses

        self.assertEqual(self.api.try_get_size('file.txt'), 76861)

    def test_getting_invalid_size(self):
        responses = [
            Response(200, 'Mode was switched to binary'),
            Response(200, '76861 bytes'),
            Response(200, 'Mode was switched to ascii')]
        self.response_mock.side_effect = responses

        self.assertEqual(self.api.try_get_size('file.txt'), -1)

    def test_list_files_raw_in_active_mode(self):
        responses = [
            Response(200, 'PORT command successful'),
            Response(150, 'Opening ASCII mode data connection for file list'),
            Response(200, 'End.')]
        self.response_mock.side_effect = responses
        self.socket_mock.getsockname.return_value = ('192.168.1.1', 666)
        self.socket_mock.recv.side_effect = [b'sample listing', b'']

        self.assertEqual(self.api.list_files_raw(), 'sample listing')

    def test_list_files_raw_in_passive_mode(self):
        responses = [
            Response(227, 'Entering Passive Mode (192,168,1,1,1,4)'),
            Response(150, 'Opening ASCII mode data connection for file list'),
            Response(200, 'End.')]
        self.response_mock.side_effect = responses
        self.socket_mock.recv.side_effect = [b'sample listing', b'']

        self.assertEqual(self.api.list_files_raw(), 'sample listing')

    def test_list_files(self):
        listing = (
            '-rw-rw-r--   1 ftp      ftp       9967461 08:00 01-Globus.mp3\r\n'
            '-rw-rw-r--   1 ftp      ftp       5525649 Dec 10  2007 02   Gospo'
            'da demokraty.mp3\r\ndrw-rw-r--   1 ftp      ftp       8650309 Dec'
            ' 11  2007 03 Byvshiy podjesaul.mp3\r\n-rw-rw-r--   1 ftp      ftp'
            '      12458333 15:32 07-Letniy dozhd.mp3\r\ndrw-rw-r--   1 ftp   '
            '   ftp       8245331 Dec 11  2007 11-Byvshiy podjesaul (1-y varia'
            'nt fonogrammy).mp3\r\n')

        with mock.patch.object(FtpApi, 'list_files_raw', return_value=listing):
            expected = [
                ('01-Globus.mp3', True),
                ('02   Gospoda demokraty.mp3', True),
                ('03 Byvshiy podjesaul.mp3', False),
                ('07-Letniy dozhd.mp3', True),
                ('11-Byvshiy podjesaul (1-y variant fonogrammy).mp3', False)]

            self.assertEqual(self.api.list_files(), expected)

    def test_file_downloading(self):
        file_size = 100000
        responses = [
            Response(200, 'Type set to I'),
            Response(213, str(file_size)),
            Response(200, 'Type set to A'),
            Response(200, 'Type set to I'),
            Response(150, 'Opening BINARY mode data connection for file')]
        self.response_mock.side_effect = responses
        with mock.patch.object(Talker, '_open_data_connection',
                               return_value=None):
            with mock.patch.object(Talker, '_read_data') as data_mock:
                data_mock.return_value = (b'x' for i in range(file_size))

                actual = b''.join(self.api.get_file('file.txt'))
                self.assertEqual(len(actual), file_size)
                self.assertEqual(actual, b'x' * file_size)
