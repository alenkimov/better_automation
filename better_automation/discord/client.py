from random import choice
from typing import Any
from time import time
import string

from curl_cffi import requests
from yarl import URL

from .account import DiscordAccount, DiscordAccountStatus
from .errors import (
    HTTPException,
    BadRequest,
    Unauthorized,
    CaptchaRequired,
    RateLimited,
    Forbidden,
    NotFound,
    DiscordServerError,
)
from ..base import BaseClient


def generate_nonce() -> str:
    ts = time()
    return str((int(ts) * 1000 - 1420070400000) * 4194304)


def generate_session_id() -> str:
    return "".join(choice(string.ascii_letters + string.digits) for _ in range(32))


def json_or_text(response: requests.Response) -> dict[str, Any] or str:
    try:
        if response.headers['content-type'] == 'application/json':
            return response.json()
    except KeyError:
        # Thanks Cloudflare
        pass

    return response.text


class DiscordClient(BaseClient):
    BASE_URL = f"https://discord.com"
    API_VERSION = 9
    BASE_API_URL = f"{BASE_URL}/api/v{API_VERSION}"
    DEFAULT_HEADERS = {
        "authority": "discord.com",
        "accept": "*/*",
        "accept-language": "en-US,en;q=0.9",
        "origin": "https://discord.com",
        "referer": "https://discord.com/channels/@me",
        "connection": "keep-alive",
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-ch-ua": '"Chromium";v="110", "Not A(Brand";v="24", "Google Chrome";v="110"',
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "x-debug-options": "bugReporterEnabled",
        "x-discord-locale": "en-US",
    }

    def __init__(
            self,
            account: DiscordAccount,
            **session_kwargs,
    ):
        super().__init__(**session_kwargs)
        self.account = account

    async def request(
            self,
            method,
            url,
            **kwargs,
    ) -> tuple[requests.Response, dict[str, Any] or str]:
        headers = kwargs.pop("headers", {})
        headers["authorization"] = self.account.auth_token

        response = await self.session.request(
            method,
            url,
            headers=headers,
            **kwargs,
        )

        data = json_or_text(response)

        if response.status_code == 400:
            if data.get("captcha_key"):
                raise CaptchaRequired(response, data)
            raise BadRequest(response, data)

        if response.status_code == 401:
            self.account.status = DiscordAccountStatus.BAD_TOKEN
            raise Unauthorized(response, data)

        if response.status_code == 403:
            raise Forbidden(response, data)

        if response.status_code == 404:
            raise NotFound(response, data)

        if response.status_code == 429:
            if not response.headers.get("via") or isinstance(data, str):
                # Banned by Cloudflare more than likely.
                raise HTTPException(response, data)

            retry_after = data["retry_after"]
            raise RateLimited(retry_after)

        if response.status_code >= 500:
            raise DiscordServerError(response, data)

        if not 200 <= response.status_code < 300:
            raise HTTPException(response, data)

        if "flags" in data and "public_flags" in data:
            flags_data = data['flags'] - data['public_flags']

            if flags_data == 17592186044416:
                self.account.is_quarantined = True
            elif flags_data == 1048576:
                self.account.is_spammer = True
            elif flags_data == 17592186044416 + 1048576:
                self.account.is_spammer = True
                self.account.is_quarantined = True

        self.account.status = DiscordAccountStatus.GOOD
        return response, data

    async def bind_app(
            self,
            *,
            client_id: str,
            scope: str,
            state: str = None,
            response_type: str = "code",
    ):
        url = f"{self.BASE_API_URL}/oauth2/authorize"
        params = {
            "client_id": client_id,
            "response_type": response_type,
            "scope": scope,
        }
        if state: params["state"] = state
        payload = {
            "permissions": "0",
            "authorize": True,
        }
        response, data = await self.request("POST", url, json=payload, params=params)
        bind_url = URL(data["location"])
        bind_code = bind_url.query.get("code")
        return bind_code

    async def send_guild_chat_message(
            self,
            guild_id: int | str,
            channel_id: int | str,
            message: str,
    ) -> int:
        """
        :param guild_id: ID Сервера.
        :param channel_id: ID Канала.
        :param message: Сообщение.
        :return: ID сообщения.
        """
        url = f"{self.BASE_API_URL}/channels/{channel_id}/messages"
        headers = {
            "referer": f"{self.BASE_URL}/channels/{guild_id}/{channel_id}",
        }
        payload = {
            "mobile_network_type": "unknown",
            "content": message,
            "nonce": generate_nonce(),
            "tts": False,
            "flags": 0,
        }
        response, data = await self.request("POST", url, json=payload, headers=headers)
        message_id = data["id"]
        return message_id

    async def send_reaction(
            self,
            channel_id: int | str,
            message_id: int | str,
            emoji: str,
    ):
        """
        :param channel_id: ID Канала.
        :param message_id: ID Сообщения.
        :param emoji: Реакция. Например: ✅, ❤️, 👍, 🇷🇺
        """
        url = f"{self.BASE_API_URL}/channels/{channel_id}/messages/{message_id}/reactions/{emoji}/@me"
        await self.request("PUT", url)

    async def press_button(
            self,
            guild_id: int | str,
            channel_id: int | str,
            message_id: int | str,
            application_id: int | str,
            button_data: dict,
    ):
        url = f"{self.BASE_API_URL}/interactions"
        headers = {
            'authority': 'discord.com',
            'accept': '*/*',
            'content-type': 'application/json',
            'origin': 'https://discord.com',
            'referer': f'https://discord.com/channels/{guild_id}/{channel_id}',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin',
            'x-debug-options': 'bugReporterEnabled',
            'x-discord-locale': 'en-US',
        }
        payload = {
            'type': 3,
            'nonce': generate_nonce(),
            'guild_id': guild_id,
            'channel_id': channel_id,
            'message_flags': 0,
            'message_id': message_id,
            'application_id': application_id,
            'session_id': generate_session_id(),
            'data': {
                'component_type': button_data['type'],
                'custom_id': button_data['custom_id'],
            }
        }
        response, data = await self.request("POST", url, headers=headers, json=payload)
        return data

    # get messages
    async def request_messages(
            self,
            channel_id: int | str,
            limit: int = 50,
            before_date: str = None,
            around_message_id: int | str = None,
            after_message_id: int | str = None,
    ) -> list[dict]:
        """
        :param limit: between 1 and 100
        :param before_date: snowflake
        :return: Message data
        """
        url = f"{self.BASE_API_URL}/channels/{channel_id}/messages"
        params = {
            "limit": limit,
        }
        if before_date: params["before"] = before_date
        if around_message_id: params["around"] = around_message_id
        if after_message_id: params["after"] = after_message_id
        response, data = await self.request("GET", url, params=params)
        return data

    async def request_message(self, channel_id: int | str, message_id: int | str) -> dict:
        messages = await self.request_messages(channel_id, limit=1, around_message_id=message_id)
        return messages[0]
