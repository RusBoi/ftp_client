import unittest
import client
import ftplib


TEST_HOST = 'speedtest.tele2.net'


class TestClient(unittest.TestCase):
    def setUp(self):
        self.ftp = ftplib.FTP(TEST_HOST, 21)

    def test_read_line(self):
        pass


if __name__ == '__main__':
    unittest.main()