import json
class OnionError(Exception):
    def __init__(self, code: str, message: str):
        self.code, self.message = code, message
        super().__init__(json.dumps({"code": code, "message": message}))
