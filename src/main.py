from ftp import FTP


# f = FTP('shannon.usu.edu.ru', verbose_output=True)
f = FTP('speedtest.tele2.net', verbose_output=True)
f.login()
data = f.get_file('20MB.zip')
