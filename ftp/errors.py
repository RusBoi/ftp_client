class Error(Exception):
    pass


class WrongResponse(Error):
    def __init__(self, response):
        self.response = response
