from datetime import datetime


def parse_datetime(created_at_str: str) -> datetime:
    return datetime.strptime(created_at_str, '%a %b %d %H:%M:%S +0000 %Y')


class UserData:
    def __init__(self, data: dict):
        self._data = data
        self._created_at = parse_datetime(self._data["legacy"]["created_at"])
        self._id = int(data["rest_id"])

    def __str__(self):
        return f"({self.id}) @{self.username}"

    @property
    def data(self) -> dict | None:
        return self._data

    @property
    def created_at(self) -> datetime | None:
        return self._created_at

    @property
    def id(self) -> int | None:
        return self._id

    @property
    def username(self) -> str | None:
        return self._data["legacy"]["screen_name"]

    @property
    def name(self) -> str:
        return self._data["legacy"]["name"]

    @property
    def followers_count(self) -> int:
        return self._data['legacy']['followers_count']
