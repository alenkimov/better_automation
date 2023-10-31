from typing import Any

from yarl import URL
import aiohttp


class Client:
    DEFAULT_HEADERS = {
        "authority": "discord.com",
        "accept": "*/*",
        "accept-language": "en-IN,en;q=0.9",
        "content-type": "application/json",
        "origin": "https://discord.com",
    }

    def __init__(
            self,
            auth_token: str,
            session: aiohttp.ClientSession,
    ):
        self.auth_token = auth_token
        self.session = session

    async def request(
            self,
            method,
            url,
            params: dict = None,
            headers: dict = None,
            json: Any = None,
            data: Any = None,
    ) -> aiohttp.ClientResponse:
        full_headers = headers or {}
        full_headers.update(self.DEFAULT_HEADERS)
        full_headers["authorization"] = self.auth_token

        return await self.session.request(
            method,
            url,
            params=params,
            json=json,
            headers=full_headers,
            data=data,
        )

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

        bind_url = URL(bind_url)
        code = bind_url.query.get("code")

        if code is None:
            raise ValueError(f"Bind url doesn't contain a bind code."
                             f"\n\tBind url: '{bind_url}'")

        return code
