class Response:
    def __init__(self, code, message):
        self.code = code
        self.message = message
        self.success = self.code // 100 in [1, 2, 3]

    def __repr__(self):
        return '{}: {}'.format(self.code, self.message)

    def __str__(self):
        return self.__repr__()
