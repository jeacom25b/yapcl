
class ParserError(BaseException):
    def __init__(self, expected, index):
        self.expected = expected
        self.index = index
        self.message = None

    def __str__(self):
        if self.message:
            return f'{self.message}\nat index {self.index}'
        return f'expected {self.expected} at index {self.index}'
