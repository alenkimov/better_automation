from pydantic import BaseModel
from datetime import datetime


class TwitterUserData(BaseModel):
    id: int
    username: str
    name: str
    created_at: datetime
    description: str
    location: str
    followers_count: int
    followings_count: int
    raw_data: dict

    def __str__(self):
        return f"({self.id}) @{self.username}"

    @classmethod
    def from_raw_user_data(cls, data: dict):
        legacy = data["legacy"]
        values = {
            "id": int(data["rest_id"]),
            "username": legacy["screen_name"],
            "name": legacy["name"],
            "created_at": datetime.strptime(legacy["created_at"], '%a %b %d %H:%M:%S +0000 %Y'),
            "description": legacy["description"],
            "location": legacy["location"],
            "followers_count": legacy["followers_count"],
            "followings_count": legacy["friends_count"],
            "raw_data": data,
        }
        return cls(**values)
