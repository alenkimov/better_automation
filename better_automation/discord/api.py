from ..http_client import BetterClientSession


class DiscordAPI(BetterClientSession):
    DEFAULT_HEADERS = {
        "authority": "discord.com",
        "accept": "*/*",
        "accept-language": "en-IN,en;q=0.9",
        "content-type": "application/json",
        "origin": "https://discord.com",
    }

    def __init__(self, auth_token: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.headers.update(self.DEFAULT_HEADERS)
        self._auth_token = None
        self.set_auth_token(auth_token)

    def set_auth_token(self, auth_token: str):
        self._auth_token = auth_token
        self.headers.update({"authorization": auth_token})

    @property
    def auth_token(self) -> str | None:
        return self._auth_token

    async def bind_app(
            self,
            client_id: str,
            response_type: str = "code",
            scope: str = "identify guilds guilds.members.read",
    ):
        url = "https://discord.com/api/v9/oauth2/authorize"
        querystring = {
            "client_id": client_id,
            "response_type": response_type,
            "scope": scope,
        }
        payload = {
            "permissions": "0",
            "authorize": True,
        }
        response = await self.post(url, json=payload, params=querystring)
        data = await response.json()
        code = data["location"].split("=")[1]
        return code
