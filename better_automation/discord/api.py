from urllib.parse import urlparse, parse_qs

import aiohttp

from ..http import BetterHTTPClient


class DiscordAPI(BetterHTTPClient):
    DEFAULT_HEADERS = {
        "authority": "discord.com",
        "accept": "*/*",
        "accept-language": "en-IN,en;q=0.9",
        "content-type": "application/json",
        "origin": "https://discord.com",
    }

    def __init__(self, session: aiohttp.ClientSession, auth_token: str, *args, **kwargs):
        super().__init__(session, *args, **kwargs)
        self._headers.update(self.DEFAULT_HEADERS)
        self._auth_token = None
        self.set_auth_token(auth_token)

    def set_auth_token(self, auth_token: str):
        self._auth_token = auth_token
        self._headers.update({"authorization": auth_token})

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
        response = await self.request("POST", url, json=payload, params=querystring)
        data = await response.json()

        bind_url = data.get("location")
        if bind_url is None:
            raise ValueError(f"Response data doesn't contain a bind url."
                             f"\n\tResponse data: {data}")

        parsed_url = urlparse(bind_url)
        query = parse_qs(parsed_url.query)
        code = query.get("code", [None])[0]

        if code is None:
            raise ValueError(f"Bind url doesn't contain a bind code."
                             f"\n\tBind url: '{bind_url}'")

        return code
