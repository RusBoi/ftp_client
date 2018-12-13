from ftp.parser import Parser
from ftp.client import Client


if __name__ == '__main__':
    args = Parser.parse_arguments()
    Client.setup(args)
    Client.run()
