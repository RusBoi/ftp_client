import unittest
import unittest.mock as mock
import socket
import client
import ftplib


def blank(*args, **kwargs):
    pass


class DownloadingFiles(unittest.TestCase):

    def test_read_line(self):
        with mock.patch('socket.socket.recv') as recv:
            recv.return_value = b'hello!\r\n'
            real = ftplib.FtpClient('localhost', 21, print_input=False,
                              print_output=False).read_line()

        expected = 'hello'
        self.assertEqual(real, expected)


if __name__ == '__main__':
    unittest.main()
