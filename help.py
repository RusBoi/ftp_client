GET_HELP = """
usage: get [-r] <path>
Receive file from the server
optional arguments:
-r\t\tReceive whole directory from the server
"""

PUT_HELP = """
usage: put [-r] <path>
Send file to the server
optional arguments:
-r\t\tSend whole directory to the server
"""

USER_HELP = """
usage: user <username>
Send new user information
"""

PWD_HELP = """
Print current directory on remote machine
"""

RM_HELP = """
usage: rm [-r] <path>
Remove file on the remote machine
optional arguments:
-r\t\tremove directory
"""

REN_HELP = """
usage: ren <file name>
Rename file
"""

CD_HELP = """
usage: cd <path>
Change remote working directory
"""

MKDIR_HELP = """
usage: mkdir <directory name>
Make directory on the remote machine
"""

LS_HELP = """
usage: ls [-l] [<path>]
Show content of remote directory
opitonal arguments:
-l\t\tShow content in list
"""

SIZE_HELP = """
usage: size <file_name>
Show size of remote file
"""

DEBUG_HELP = """
Toggle debugging mode
"""

MODE_HELP = """
Enter passive or active transfer mode
"""

HELP_HELP = """
usage: help [<command>]
Print local help information about command. If command isn't specified show all available commands
"""

EXIT_HELP = """
Terminate ftp session and exit
"""
