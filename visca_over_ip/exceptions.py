class ViscaException(RuntimeError):
    """Raised when the camera doesn't like a message that it received"""

    def __init__(self, response_body):
        if isinstance(response_body, bytes) and len(response_body) >= 3:
            self.status_code = response_body[2]
        else:
            self.status_code = -1

        descriptions = {
            1: 'Message length error',
            2: 'Syntax error',
            3: 'Command buffer full',
            4: 'Command cancelled',
            5: 'No socket',
            0x41: 'Command not executable',
            # EC20 specific error codes
            0x76: 'Position limit exceeded or command blocked',  # 118 decimal
        }
        self.description = descriptions.get(self.status_code, f'Unknown error code 0x{self.status_code:02x}')

        super().__init__(f'Error when executing command: {self.description}')


class NoQueryResponse(TimeoutError):
    """Raised when a response cannot be obtained to a query after a number of retries"""
