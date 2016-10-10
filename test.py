import unittest
import client
import ftplib


def blank(*args, **kwargs):
    pass


class DownloadingFiles(unittest.TestCase):
    def SetUp(self):
        self.ftp = ftplib.FTP('speedtest.tele2.net', 21, printout=blank)

    def TearUp(self):
        del self.ftp

    def test_download_small_files(self):
        pass

if __name__ == '__main__':
    unittest.main()