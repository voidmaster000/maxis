"""
Warn class for storing user warnings
"""


class Warn:
    def __init__(self, cause: str = "", user_id: int = 0):
        self.warn_causes: list[str] = []
        self.warns = 0
        self.user_id = user_id

        if cause:
            self.new_warn(cause)

    def new_warn(self, cause: str):
        """Add a new warning"""
        self.warns += 1
        self.warn_causes.append(cause)
