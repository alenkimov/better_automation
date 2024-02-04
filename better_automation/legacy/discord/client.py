import datetime
from functools import wraps
from random import choice
from typing import Any, Literal
from time import time
import string

from twitter.base import BaseClient
from curl_cffi import requests
from yarl import URL

from .x_properties import create_guild_x_context_properties, create_x_super_properties, encode_x_properties
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


def generate_nonce() -> str:
    return str((int(time()) * 1000 - 1420070400000) * 4194304)


def generate_session_id() -> str:
    return "".join(choice(string.ascii_letters + string.digits) for _ in range(32))


def json_or_text(response: requests.Response) -> dict[str, Any] or str:
    try:
        if response.headers["content-type"] == "application/json":
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
        "origin": "https://discord.com",
        "x-debug-options": "bugReporterEnabled",
    }
    CLIENT_BUILD_NUMBER = 255423

    def __init__(
            self,
            account: DiscordAccount,
            *,
            locale: str = "en-US",
            **session_kwargs,
    ):
        super().__init__(**session_kwargs)
        self.account = account
        self.x_super_properties = create_x_super_properties(self._session.user_agent, self.CLIENT_BUILD_NUMBER)
        self._session.cookies.set("locale", locale, "discord.com", "/")
        self._session.headers.update({
            "x-discord-locale": locale,
            "accept-language": f"{locale},{locale.split('-')[0]};q=0.9",
        })

    async def request(
            self,
            method,
            url,
            **kwargs,
    ) -> tuple[requests.Response, dict[str, Any] or str]:
        headers = kwargs["headers"] = kwargs.get("headers") or {}
        headers["authorization"] = self.account.auth_token
        headers["x-super-properties"] = self.x_super_properties

        response = await self._session.request(method, url, **kwargs)
        data = json_or_text(response)

        if response.status_code == 401:
            self.account.status = DiscordAccountStatus.BAD_TOKEN
            raise Unauthorized(response, data)

        if response.status_code == 404:
            raise NotFound(response, data)

        if response.status_code >= 500:
            raise DiscordServerError(response, data)

        self.account.status = DiscordAccountStatus.GOOD

        if response.status_code == 400:
            if data.get("captcha_key"):
                raise CaptchaRequired(response, data)
            raise BadRequest(response, data)

        if response.status_code == 403:
            # May be BAD_TOKEN
            raise Forbidden(response, data)

        if response.status_code == 429:
            if not response.headers.get("via") or isinstance(data, str):
                # Banned by Cloudflare more than likely.
                raise HTTPException(response, data)
            raise RateLimited(response, data)

        if not 200 <= response.status_code < 300:
            raise HTTPException(response, data)

        if "flags" in data and "public_flags" in data:
            flags_data = data["flags"] - data["public_flags"]

            if flags_data == 17592186044416:
                self.account.is_quarantined = True
            elif flags_data == 1048576:
                self.account.is_spammer = True
            elif flags_data == 17592186044416 + 1048576:
                self.account.is_spammer = True
                self.account.is_quarantined = True

        return response, data

    # APP - BINDING

    async def bind_app(
            self,
            *,
            client_id: str,
            scope: str,
            state: str = None,
            response_type: str = "code",
    ):
        """
        Binds an application to the user's account using OAuth2.
        :param client_id: Client ID of the application.
        :param scope: The scope of the access request.
        :param state: An optional state parameter.
        :param response_type: The type of response required, defaults to 'code'.
        :return: The authorization code as part of the binding process.
        """
        url = f"{self.BASE_API_URL}/oauth2/authorize"
        params = {
            "client_id": client_id,
            "response_type": response_type,
            "scope": scope,
        }
        if state:
            params["state"] = state
        payload = {
            "permissions": "0",
            "authorize": True,
        }
        response, data = await self.request("POST", url, json=payload, params=params)
        bind_url = URL(data["location"])
        bind_code = bind_url.query.get("code")
        return bind_code

    # GUILD

    async def send_guild_chat_message(
            self,
            guild_id: int | str,
            channel_id: int | str,
            message: str,
    ) -> int:
        """
        Sends a message to a specified guild channel.
        :param guild_id: ID of the guild.
        :param channel_id: ID of the channel in the guild.
        :param message: The message content to send.
        :return: The ID of the sent message.
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
        Sends a reaction to a specific message in a channel.
        :param channel_id: ID of the channel.
        :param message_id: ID of the message to react to.
        :param emoji: The emoji to use for the reaction.
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
        """
        Simulates pressing a button in a message (such as for interactions).
        :param guild_id: ID of the guild.
        :param channel_id: ID of the channel.
        :param message_id: ID of the message containing the button.
        :param application_id: ID of the application associated with the button.
        :param button_data: Data of the button being pressed.
        :return: Response data from the button press.
        """
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

    async def request_messages(
            self,
            channel_id: int | str,
            limit: int = 50,
            before_date: str = None,
            around_message_id: int | str = None,
            after_message_id: int | str = None,
    ) -> list[dict]:
        """
        Retrieves a list of messages from a specified channel.
        :param channel_id: ID of the channel.
        :param limit: The number of messages to retrieve (between 1 and 100).
        :param before_date: Get messages before this date (snowflake format).
        :param around_message_id: Get messages around this message ID.
        :param after_message_id: Get messages after this message ID.
        :return: A list of message data.
        """
        url = f"{self.BASE_API_URL}/channels/{channel_id}/messages"
        params = {"limit": limit}
        if before_date: params["before"] = before_date
        if around_message_id: params["around"] = around_message_id
        if after_message_id: params["after"] = after_message_id
        response, data = await self.request("GET", url, params=params)
        return data

    async def request_message(self, channel_id: int | str, message_id: int | str) -> dict:
        """
        Retrieves a specific message from a channel.
        :param channel_id: ID of the channel.
        :param message_id: ID of the message to retrieve.
        :return: Data of the requested message.
        """
        messages = await self.request_messages(channel_id, limit=1, around_message_id=message_id)
        return messages[0]

    async def request_invite_data(self, invite_code: str) -> dict:
        """
        Retrieves data for a specific invite code.
        :param invite_code: The invite code to retrieve data for.
        :return: Data associated with the invite code.
        """
        url = f"{self.BASE_API_URL}/invites/{invite_code}"
        params = {
            "with_counts": "true",
            "with_expiration": "true",
        }
        headers = {'referer': f'https://discord.com/invite/{invite_code}'}

        response, data = await self.request("GET", url, headers=headers, params=params)
        return data

    @staticmethod
    def check_cf_cookies(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            # if not all(key in self.session.cookies for key in ("__cfruid", "__dcfduid")):
            if {"__cfruid", "__dcfduid"} <= self._session.cookies.keys():
                return await func(self, *args, **kwargs)
            else:
                raise ValueError("This action needs Cloudflare Cookies (__cfruid, __dcfduid) to bypass the captcha.")
        return wrapper

    @check_cf_cookies
    async def join_guild(
            self,
            invite_code: str,
            guild_id: int | str,
            channel_id: int | str,
            channel_type: int = 0,
            captcha_response: str = None,
            captcha_rqtoken: str = None,
    ) -> dict:
        """
        Joins a guild using an invite code.
        :param invite_code: The invite code of the guild to join.
        :param guild_id: The ID of the guild.
        :param channel_id: The ID of the channel in the guild.
        :param channel_type: The type of the channel.
        :param captcha_response: CAPTCHA response if required.
        :param captcha_rqtoken: CAPTCHA request token if required.
        :return: Response data after joining the guild.
        """
        url = f"{self.BASE_API_URL}/invites/{invite_code}"
        payload = {"session_id": None}
        headers = {
            'referer': f'https://discord.com/invite/{invite_code}',
            'x-context-properties': create_guild_x_context_properties(guild_id, channel_id, channel_type),
        }
        if captcha_response and captcha_rqtoken:
            headers["x-captcha-key"] = captcha_response
            headers["x-captcha-rqtoken"] = captcha_rqtoken

        response, data = await self.request("POST", url, headers=headers, json=payload)
        return data

    async def join_guild_with_invite_data(
            self,
            invite_data: dict,
            captcha_response: str = None,
            captcha_rqtoken: str = None,
    ) -> dict:
        """
        Joins a guild using invite data.
        :param invite_data: Dictionary containing invite data, including code, guild_id, and channel.
        :param captcha_response: CAPTCHA response if required.
        :param captcha_rqtoken: CAPTCHA request token if required.
        :return: Response data after joining the guild.
        """
        return await self.join_guild(
            invite_data["code"],
            invite_data["guild_id"],
            invite_data["channel"]["id"],
            channel_type=invite_data["channel"]["type"],
            captcha_response=captcha_response,
            captcha_rqtoken=captcha_rqtoken,
        )

    async def leave_guild(self, guild_id: int | str):
        """
        Leaves a guild.
        :param guild_id: The ID of the guild to leave.
        """
        url = f"{self.BASE_API_URL}/users/@me/guilds/{guild_id}"
        payload = {"lurking": False}
        await self.request("DELETE", url, json=payload)

    async def _request_guild_rules_form(
            self,
            invite_code: str,
            guild_id: int | str,
    ):
        url = f"{self.BASE_API_URL}/guilds/{guild_id}/member-verification"
        params = {
            "with_guild": "false",
            "invite_code": invite_code,
        }
        response, data = await self.request("GET", url, params=params)
        return data

    async def _agree_guild_rules(
            self,
            guild_id: int | str,
            channel_id: int | str,
            rules_form: dict,
    ):
        url = f"{self.BASE_API_URL}/guilds/{guild_id}/requests/@me"
        headers = {
            "referrer": f'https://discord.com/channels/{guild_id}/{channel_id}'
        }
        form_fields = rules_form["form_fields"][0].copy()
        form_fields["response"] = True
        payload = {
            "version": rules_form["version"],
            "form_fields": [form_fields],
        }
        response, data = await self.request("PUT", url, headers=headers, json=payload)
        return data

    async def agree_guild_rules(
            self,
            invite_code: str,
            guild_id: int | str,
            channel_id: int | str,
    ):
        """
        Agrees to the rules of a guild based on an invite code.
        :param invite_code: The invite code of the guild.
        :param guild_id: The ID of the guild.
        :param channel_id: The ID of the channel in the guild.
        :return: Response data after agreeing to the guild rules.
        """
        rules_form = await self._request_guild_rules_form(invite_code, guild_id)
        return await self._agree_guild_rules(guild_id, channel_id, rules_form)

    async def agree_guild_rules_with_invite_data(self, invite_data: dict):
        """
        Agrees to the rules of a guild using invite data.
        :param invite_data: A dictionary containing invite data, including code, guild_id, and channel.
        :return: Response data after agreeing to the guild rules.
        """
        return await self.agree_guild_rules(
            invite_data["code"],
            invite_data["guild_id"],
            invite_data["channel"]["id"]
        )

    async def create_invite_code(
            self,
            channel_id: int | str,
            *,
            max_age_seconds: int = 0,
            max_users: int = 0,
            grant_temporary_membership: bool = False,
            invite_code_to_validate: str = None,
            target_type: str = None,
    ) -> dict:
        """
        Creates an invite code for a specific channel.
        :param channel_id: ID of the channel to create the invite for.
        :param max_age_seconds: Duration in seconds for which the invite is valid.
        :param max_users: Maximum number of users that can use the invite.
        :param grant_temporary_membership: If true, users who join via the invite are granted temporary membership.
        :param invite_code_to_validate: An existing invite code to validate against.
        :param target_type: The type of target for the invite.
        :return: Data about the created invite code.
        """
        url = f"{self.BASE_API_URL}/channels/{channel_id}/invites"
        payload = {
            "max_age": max_age_seconds,
            "max_users": max_users,
            "temporary": grant_temporary_membership,
            "target_type": target_type
        }
        headers = {
            "x-context-properties": encode_x_properties({"location": "Hub Sidebar"}),
        }
        if invite_code_to_validate: payload["validate"] = invite_code_to_validate
        response, data = await self.request("POST", url, headers=headers, json=payload)
        return data

    async def delete_invite_code(self, invite_code: str):
        """
        Deletes an invite code. Note: This operation might not work and return a 404 error.
        :param invite_code: The invite code to be deleted.
        """
        url = f"{self.BASE_API_URL}/invites/{invite_code}"
        await self.request("DELETE", url)

    async def request_guild_invites(self, guild_id: int | str) -> int:
        """
        Retrieves a list of invite codes for a specific guild.
        :param guild_id: ID of the guild.
        :return: List of invite codes.
        """
        url = f"{self.BASE_API_URL}/guilds/{guild_id}/invites"
        response, data = await self.request("GET", url)
        return data

    async def reqeust_channel_invites(self, channel_id: int | str) -> int:
        """
        Retrieves a list of invite codes for a specific channel.
        :param channel_id: ID of the channel.
        :return: List of invite codes.
        """
        url = f"{self.BASE_API_URL}/channels/{channel_id}/invites"
        response, data = await self.request("GET", url)
        return data

    async def x_track_get_request(self, url, **request_kwargs):
        """
        Sends a GET request with 'x-track' header. This might be necessary for some endpoints.
        :param url: URL for the GET request.
        :param request_kwargs: Additional kwargs for the request.
        :return: Response data.
        """
        request_kwargs["headers"] = request_kwargs.get("headers", {})
        request_kwargs["headers"]["x-track"] = self.x_super_properties
        return await self.request("GET", url, **request_kwargs)

    async def request_guilds(self, with_counts: bool = True):
        """
        Retrieves a list of guilds the user is a member of.
        :param with_counts: Boolean to include count information.
        :return: List of guilds.
        """
        url = f"{self.BASE_API_URL}/users/@me/guilds"
        params = {"with_count": "true"} if with_counts else None
        response, data = await self.x_track_get_request(url, params=params)
        return data

    async def request_guild_channels(self, guild_id: int | str):
        """
        Retrieves a list of channels in a specific guild.
        :param guild_id: ID of the guild.
        :return: List of channels.
        """
        url = f"{self.BASE_API_URL}/guilds/{guild_id}/channels"
        response, data = await self.x_track_get_request(url)
        return data

    async def request_guild_roles(self, guild_id: int | str):
        """
        Retrieves a list of roles in a specific guild.
        :param guild_id: ID of the guild.
        :return: List of roles.
        """
        url = f"{self.BASE_API_URL}/guilds/{guild_id}/roles"
        response, data = await self.x_track_get_request(url)
        return data

    async def request_discoverable_guilds(self, offset: int | str = 0, limit: int | str = 48):
        """
        Retrieves a list of discoverable guilds.
        :param offset: Pagination offset.
        :param limit: Number of guilds to retrieve.
        :return: List of discoverable guilds.
        """
        url = f"{self.BASE_API_URL}/discoverable-guilds"
        params = {"offset": str(offset), "limit": str(limit)}
        response, data = await self.request("GET", url, params=params)
        return data

    async def request_guild_regions(self, guild_id):
        """
        Retrieves a list of available regions for a specific guild.
        :param guild_id: ID of the guild.
        :return: List of regions.
        """
        url = f"{self.BASE_API_URL}/guilds/{guild_id}/regions"
        response, data = await self.request("GET", url)
        return data

    # USER

    async def get_relationships(self):
        """
        Retrieves the current user's relationships.
        :return: List of relationships.
        """
        url = f"{self.BASE_API_URL}/users/@me/relationships"
        response, data = await self.request("GET", url)
        return data

    async def get_mutual_friends(self, user_id: str):
        """
        Retrieves mutual friends with a specified user.
        :param user_id: ID of the user to check mutual friends with.
        :return: List of mutual friends.
        """
        url = f"{self.BASE_API_URL}/users/{user_id}/relationships"
        response, data = await self.request("GET", url)
        return data

    async def request_friend(self, user: str):
        """
        Sends a friend request to a user or accepts a pending one.
        :param user: Username with discriminator (e.g., 'User#1234') or user ID.
        :return: Response data.
        """
        if "#" in user:
            username, discriminator = user.split("#")
            url = f"{self.BASE_API_URL}/users/@me/relationships"
            payload = {"username": username, "discriminator": int(discriminator)}
            response, data = await self.request("POST", url, json=payload)
        else:
            url = f"{self.BASE_API_URL}/users/@me/relationships/{user}"
            response, data = await self.request("PUT", url)
        return data

    async def accept_friend(self, user_id: str, location: str):
        """
        Accepts a friend request.
        :param user_id: ID of the user whose friend request is being accepted.
        :param location: Context location for the request.
        :return: Response data.
        """
        url = f"{self.BASE_API_URL}/users/@me/relationships/{user_id}"
        headers = {"X-Context-Properties": create_guild_x_context_properties(location, user_id)}
        response, data = await self.request("PUT", url, headers=headers)
        return data

    async def remove_relationship(self, user_id: str, location: str):
        """
        Removes a relationship with a user.
        :param user_id: ID of the user whose relationship is being removed.
        :param location: Context location for the request.
        :return: Response data.
        """
        url = f"{self.BASE_API_URL}/users/@me/relationships/{user_id}"
        headers = {"X-Context-Properties": create_guild_x_context_properties(location, user_id)}
        response, data = await self.request("DELETE", url, headers=headers)
        return data

    async def block_user(self, user_id: str, location: str):
        """
        Blocks a user.
        :param user_id: ID of the user to block.
        :param location: Context location for the request.
        :return: Response data.
        """
        url = f"{self.BASE_API_URL}/users/@me/relationships/{user_id}"
        body = {"type": 2}
        headers = {"X-Context-Properties": create_guild_x_context_properties(location, user_id)}
        response, data = await self.request("PUT", url, json=body, headers=headers)
        return data

    async def get_profile(self, user_id: str, with_mutual_guilds: bool = None, guild_id: int | str = None):
        """
        Retrieves a user's profile.
        :param user_id: ID of the user whose profile is being retrieved.
        :param with_mutual_guilds: Include mutual guilds in the response.
        :param guild_id: Specify a guild ID to check for mutual membership.
        :return: User's profile data.
        """
        url = f"{self.BASE_API_URL}/users/{user_id}/profile"
        params = {}
        if with_mutual_guilds is not None:
            params["with_mutual_guilds"] = str(with_mutual_guilds).lower()
        if guild_id is not None:
            params["guild_id"] = str(guild_id)
        response, data = await self.request("GET", url, params=params)
        return data

    async def request_user_data(self, with_analytics_token: bool = False):
        """
        Retrieves the current user's information.
        :param with_analytics_token: Include analytics token in the response.
        :return: Current user's data.
        """
        url = f"{self.BASE_API_URL}/users/@me"
        params = {}
        if with_analytics_token is not None:
            params["with_analytics_token"] = str(with_analytics_token).lower()
        response, data = await self.request("GET", url, params=params)
        self.account.username = data["username"]
        self.account.name = data["global_name"]
        self.account.email = data["email"]
        self.account.phone = data["phone"]
        return data

    async def get_user_affinities(self):
        """
        Retrieves the current user's user affinities.
        :return: List of user affinities.
        """
        url = f"{self.BASE_API_URL}/users/@me/affinities/users"
        response, data = await self.request("GET", url)
        return data

    async def get_guild_affinities(self):
        """
        Retrieves the current user's guild affinities.
        :return: List of guild affinities.
        """
        url = f"{self.BASE_API_URL}/users/@me/affinities/guilds"
        response, data = await self.request("GET", url)
        return data

    async def get_mentions(self, limit: int, role_mentions: bool, everyone_mentions: bool):
        """
        Retrieves mentions for the current user.
        :param limit: Number of mentions to retrieve.
        :param role_mentions: Include role mentions.
        :param everyone_mentions: Include @everyone mentions.
        :return: List of mentions.
        """
        url = f"{self.BASE_API_URL}/users/@me/mentions"
        params = {
            "limit": limit,
            "roles": str(role_mentions).lower(),
            "everyone": str(everyone_mentions).lower()
        }
        response, data = await self.request("GET", url, params=params)
        return data

    async def remove_mention_from_inbox(self, message_id: str):
        """
        Removes a mention from the user's inbox.
        :param message_id: ID of the message to remove.
        :return: Response data.
        """
        url = f"{self.BASE_API_URL}/users/@me/mentions/{message_id}"
        response, data = await self.request("DELETE", url)
        return data

    # USER - SETTINGS

    async def _set_user_data(
            self,
            payload: dict,
            captcha_response: str = None,
            captcha_rqtoken: str = None,
    ) -> dict:
        """
        :return: User data.
        """
        url = f"{self.BASE_API_URL}/users/@me"
        headers = None
        if captcha_response and captcha_rqtoken:
            headers = {
                "x-captcha-key": captcha_response,
                "x-captcha-rqtoken": captcha_rqtoken,
            }
        response, data = await self.request("PATCH", url, headers=headers, json=payload)
        return data

    @check_cf_cookies
    async def change_username(
            self,
            username: str,
            captcha_response: str = None,
            captcha_rqtoken: str = None,
    ) -> dict:
        """
        Changes the username of the current user account.
        :param username: New username to be set.
        :param captcha_response: CAPTCHA response if required.
        :param captcha_rqtoken: CAPTCHA request token if required.
        :return: Updated user data after changing the username.
        :raises ValueError: If the current password is not specified in the account.
        """
        if not self.account.password:
            raise ValueError("Specify the current password before changing username.")

        payload = {
            "username": username,
            "password": self.account.password,
        }
        data = await self._set_user_data(payload, captcha_response, captcha_rqtoken)
        self.account.username = username
        return data

    async def set_name(
            self,
            name: str,
            captcha_response: str = None,
            captcha_rqtoken: str = None,
    ) -> dict:
        """
        Sets the global name for the user account.
        :param name: New global name to be set.
        :param captcha_response: CAPTCHA response if required.
        :param captcha_rqtoken: CAPTCHA request token if required.
        :return: Updated user data after setting the global name.
        """
        payload = {"global_name": name}
        data = await self._set_user_data(payload, captcha_response, captcha_rqtoken)
        self.account.name = name
        return data

    async def set_password(
            self,
            new_password: str,
    ):
        """
        Changes the password of the current user account.
        :param new_password: New password to be set.
        :return: Updated user data after changing the password.
        :raises ValueError: If the current password is not specified in the account.
        """
        if not self.account.password:
            raise ValueError("Specify the current password before changing it.")

        url = f"{self.BASE_API_URL}/users/@me"
        headers = {
            'connection': 'keep-alive',
            'referer': url,
        }
        payload = {
            'password': self.account.password,
            'new_password': new_password,
        }
        response, data = await self.request("PATCH", url, headers=headers, json=payload)
        self.account.auth_token = data["token"]
        self.account.password = new_password
        return data

    async def set_avatar(self, encoded_image_base64: str, image_ext: Literal['png', 'gif', 'jpeg'] = 'jpeg'):
        """
        Sets the user's avatar.
        :param encoded_image_base64: Base64 encoded image string.
        :param image_ext: Image extension, defaults to 'jpeg'.
        :return: Response data.
        """
        body = {"avatar": f"data:image/{image_ext};base64,{encoded_image_base64}"}
        response, data = await self._set_user_data(body)
        return data

    async def set_profile_color(self, color: int):
        """
        Sets the user's profile color.
        :param color: The color value to set.
        :return: Response data.
        """
        body = {"accent_color": color}
        response, data = await self._set_user_data(body)
        return data

    async def set_email(self, email: str, password: str):
        """
        Sets the user's email.
        :param email: New email address.
        :param password: Current password for verification.
        :return: Response data.
        """
        body = {"email": email, "password": password}
        response, data = await self._set_user_data(body)
        return data

    async def set_discriminator(self, discriminator: int, password: str):
        """
        Sets the user's discriminator.
        :param discriminator: New discriminator value.
        :param password: Current password for verification.
        :return: Response data.
        """
        body = {"password": password, "discriminator": discriminator}
        response, data = await self._set_user_data(body)
        return data

    async def set_about_me(self, bio: str):
        """
        Sets the user's bio. Note: Requires beta program access.
        :param bio: Bio text to set.
        :return: Response data.
        """
        body = {"bio": bio}
        response, data = await self._set_user_data(body)
        return data

    async def set_banner(self, encoded_image_base64: str):
        """
        Sets the user's banner.
        :param encoded_image_base64: Base64 encoded banner image.
        :return: Response data.
        """
        body = {"banner": f"data:image/png;base64,{encoded_image_base64}"}
        response, data = await self._set_user_data(body)
        return data

    async def enable_2fa(self, code: str, secret: str, password: str):
        """
        Enables 2FA for the user account.
        :param code: 2FA code.
        :param secret: 2FA secret.
        :param password: Current password for verification.
        :return: Response data including new token and backup codes.
        """
        url = f"{self.BASE_API_URL}/users/@me/mfa/totp/enable"
        body = {"code": code, "secret": secret, "password": password}
        response, data = await self.request("POST", url, json=body)
        return data

    async def disable_2fa(self, code: str):
        """
        Disables 2FA for the user account.
        :param code: 2FA code for verification.
        :return: Response data.
        """
        url = f"{self.BASE_API_URL}/users/@me/mfa/totp/disable"
        body = {"code": code}
        response, data = await self.request("POST", url, json=body)
        return data

    async def get_backup_codes(self, password: str, regenerate: bool):
        """
        Retrieves backup codes for 2FA.
        :param password: Current password for verification.
        :param regenerate: Whether to regenerate new backup codes.
        :return: Response data with backup codes.
        """
        url = f"{self.BASE_API_URL}/users/@me/mfa/codes"
        body = {"password": password, "regenerate": regenerate}
        response, data = await self.request("POST", url, json=body)
        return data

    async def disable_account(self, password: str):
        """
        Disables the user account.
        :param password: Current password for verification.
        :return: Response data.
        """
        url = f"{self.BASE_API_URL}/users/@me/disable"
        body = {"password": password}
        response, data = await self.request("POST", url, json=body)
        return data

    async def delete_account(self, password: str):
        """
        Deletes the user account.
        :param password: Current password for verification.
        :return: Response data.
        """
        url = f"{self.BASE_API_URL}/users/@me/delete"
        body = {"password": password}
        response, data = await self.request("POST", url, json=body)
        return data

    async def set_phone(self, number: str, reason: str):
        """
        Sets the user's phone number.
        :param number: Phone number to set.
        :param reason: Reason for the change.
        :return: Response data.
        """
        url = f"{self.BASE_API_URL}/users/@me/phone"
        body = {"phone": number, "change_phone_reason": reason}
        response, data = await self.request("POST", url, json=body)
        return data

    async def validate_phone(self, number: str, code: int, password: str):
        """
        Validates the phone number for the user account.
        :param number: Phone number to validate.
        :param code: Verification code sent to the phone.
        :param password: Current password for verification.
        :return: Response data.
        """
        url = f"{self.BASE_API_URL}/phone-verifications/verify"
        body = {"phone": number, "code": str(code)}
        response, data = await self.request("POST", url, json=body)

        url = f"{self.BASE_API_URL}/users/@me/phone"
        body = {"phone_token": data["token"], "password": password}
        response, data = await self.request("POST", url, json=body)
        return data

    # USER - SETTINGS - Privacy & Safety

    async def set_dm_scan_level(self, level: int):
        """
        Sets the explicit content filter level for direct messages.
        :param level: The level of the explicit content filter.
        :return: Response data after updating the settings.
        """
        url = f"{self.BASE_API_URL}/users/@me/settings"
        body = {"explicit_content_filter": level}
        response, data = await self.request("PATCH", url, json=body)
        return data

    async def allow_dms_from_server_members(self, allow: bool, disallowed_guild_ids: list):
        """
        Configures whether to allow direct messages from server members.
        :param allow: Boolean indicating if DMs are allowed.
        :param disallowed_guild_ids: List of guild IDs to restrict DMs from.
        :return: Response data after updating the settings.
        """
        url = f"{self.BASE_API_URL}/users/@me/settings"
        body = {"restricted_guilds": disallowed_guild_ids, "default_guilds_restricted": not allow}
        if not disallowed_guild_ids:
            body.pop("restricted_guilds")
        response, data = await self.request("PATCH", url, json=body)
        return data

    async def allow_friend_requests_from(self, types: list):
        """
        Sets the preferences for receiving friend requests.
        :param types: List of types indicating who can send friend requests.
        :return: Response data after updating the settings.
        """
        url = f"{self.BASE_API_URL}/users/@me/settings"
        body = {"friend_source_flags": {"all": True, "mutual_friends": True, "mutual_guilds": True}}
        types = [i.lower().strip() for i in types]
        if "everyone" not in types:
            body["friend_source_flags"]["all"] = False
        if "mutual_friends" not in types:
            body["friend_source_flags"]["mutual_friends"] = False
        if "mutual_guilds" not in types:
            body["friend_source_flags"]["mutual_guilds"] = False
        response, data = await self.request("PATCH", url, json=body)
        return data

    async def analytics_consent(self, grant: list, revoke: list):
        """
        Manages consent for analytics data.
        :param grant: List of analytics types to grant consent for.
        :param revoke: List of analytics types to revoke consent for.
        :return: Response data after updating the consent settings.
        """
        url = f"{self.BASE_API_URL}/users/@me/consent"
        body = {"grant": grant, "revoke": revoke}
        response, data = await self.request("POST", url, json=body)
        return data

    async def allow_screen_reader_tracking(self, allow: bool):
        """
        Configures tracking for screen readers.
        :param allow: Boolean indicating if screen reader tracking is allowed.
        :return: Response data after updating the settings.
        """
        url = f"{self.BASE_API_URL}/users/@me/settings"
        body = {"allow_accessibility_detection": allow}
        response, data = await self.request("PATCH", url, json=body)
        return data

    async def request_my_data(self):
        """
        Requests a copy of the user's data from Discord.
        :return: Response data indicating the status of the data request.
        """
        url = f"{self.BASE_API_URL}/users/@me/harvest"
        response, data = await self.request("POST", url)
        return data

    # USER - SETTINGS - Connections

    async def get_connected_accounts(self):
        """
        Retrieves the accounts connected to the user's Discord account.
        :return: List of connected accounts.
        """
        url = f"{self.BASE_API_URL}/users/@me/connections"
        response, data = await self.request("GET", url)
        return data

    async def get_connection_url(self, account_type: str):
        """
        Retrieves the authorization URL for a specific connection account type.
        :param account_type: The type of the account to get the connection URL for.
        :return: Authorization URL for the specified account type.
        """
        url = f"{self.BASE_API_URL}/connections/{account_type}/authorize"
        response, data = await self.request("GET", url)
        return data

    async def enable_connection_display_on_profile(self, account_type: str, account_username: str, enable: bool):
        """
        Enables or disables the display of a connected account on the user's profile.
        :param account_type: The type of the connected account.
        :param account_username: The username of the connected account.
        :param enable: Boolean to enable or disable the display on profile.
        :return: Response data after updating the setting.
        """
        url = f"{self.BASE_API_URL}/users/@me/connections/{account_type}/{account_username}"
        body = {"visibility": enable}
        response, data = await self.request("PATCH", url, json=body)
        return data

    async def enable_connection_display_on_status(self, account_type: str, account_username: str, enable: bool):
        """
        Enables or disables the display of a connected account on the user's status.
        :param account_type: The type of the connected account.
        :param account_username: The username of the connected account.
        :param enable: Boolean to enable or disable the display on status.
        :return: Response data after updating the setting.
        """
        url = f"{self.BASE_API_URL}/users/@me/connections/{account_type}/{account_username}"
        body = {"show_activity": enable}
        response, data = await self.request("PATCH", url, json=body)
        return data

    async def remove_connection(self, account_type: str, account_username: str):
        """
        Removes a connected account from the user's Discord account.
        :param account_type: The type of the connected account to remove.
        :param account_username: The username of the connected account to remove.
        :return: Response data after removing the connection.
        """
        url = f"{self.BASE_API_URL}/users/@me/connections/{account_type}/{account_username}"
        response, data = await self.request("DELETE", url)
        return data

    # USER - BILLING SETTINGS

    async def get_billing_history(self, limit: int):
        """
        Retrieves the billing history of the user.
        :param limit: The number of billing records to retrieve.
        :return: Billing history data.
        """
        url = f"{self.BASE_API_URL}/users/@me/billing/payments?limit={limit}"
        response, data = await self.request("GET", url)
        return data

    async def get_payment_sources(self):
        """
        Retrieves the payment sources associated with the user's account.
        :return: List of payment sources.
        """
        url = f"{self.BASE_API_URL}/users/@me/billing/payment-sources"
        response, data = await self.request("GET", url)
        return data

    async def get_billing_subscriptions(self):
        """
        Retrieves the billing subscriptions associated with the user's account.
        :return: List of billing subscriptions.
        """
        url = f"{self.BASE_API_URL}/users/@me/billing/subscriptions"
        response, data = await self.request("GET", url)
        return data

    async def get_stripe_client_secret(self):
        """
        Retrieves the Stripe client secret for adding new payment methods.
        Note: This method is for Stripe integration and requires Stripe API setup.
        :return: Stripe client secret data.
        """
        url = f"{self.BASE_API_URL}/users/@me/billing/stripe/setup-intents"
        response, data = await self.request("POST", url)
        return data

    # USER - APP SETTINGS - Appearance

    async def set_theme(self, theme: str):
        """
        Sets the theme of the user's Discord interface.
        :param theme: The theme to set ('light' or 'dark').
        :return: Response data after updating the theme setting.
        """
        url = f"{self.BASE_API_URL}/users/@me/settings"
        body = {"theme": theme.lower()}
        response, data = await self.request("PATCH", url, json=body)
        return data

    async def set_message_display(self, cozy_or_compact: str):
        """
        Sets the message display format in Discord.
        :param cozy_or_compact: 'Cozy' for cozy display format or 'Compact' for compact display format.
        :return: Response data after updating the message display setting.
        """
        url = f"{self.BASE_API_URL}/users/@me/settings"
        is_compact = cozy_or_compact.lower() == "compact"
        body = {"message_display_compact": is_compact}
        response, data = await self.request("PATCH", url, json=body)
        return data

    # USER - APP SETTINGS - Accessibility

    async def enable_gif_auto_play(self, enable: bool):
        """
        Enables or disables automatic GIF playback.
        :param enable: Boolean indicating whether to enable or disable GIF auto-play.
        :return: Response data after updating the setting.
        """
        url = f"{self.BASE_API_URL}/users/@me/settings"
        body = {"gif_auto_play": enable}
        response, data = await self.request("PATCH", url, json=body)
        return data

    async def enable_animated_emoji(self, enable: bool):
        """
        Enables or disables animated emojis.
        :param enable: Boolean indicating whether to enable or disable animated emojis.
        :return: Response data after updating the setting.
        """
        url = f"{self.BASE_API_URL}/users/@me/settings"
        body = {"animate_emoji": enable}
        response, data = await self.request("PATCH", url, json=body)
        return data

    async def set_sticker_animation(self, setting: str):
        """
        Sets the sticker animation preference.
        :param setting: String indicating the sticker animation setting ('always', 'interaction', 'never').
        :return: Response data after updating the setting.
        """
        url = f"{self.BASE_API_URL}/users/@me/settings"
        animation_settings = {"always": 0, "interaction": 1, "never": 2}
        body = {"animate_stickers": animation_settings.get(setting.lower(), 0)}
        response, data = await self.request("PATCH", url, json=body)
        return data

    async def enable_tts(self, enable: bool):
        """
        Enables or disables Text-To-Speech (TTS) commands.
        :param enable: Boolean indicating whether to enable or disable TTS commands.
        :return: Response data after updating the setting.
        """
        url = f"{self.BASE_API_URL}/users/@me/settings"
        body = {"enable_tts_command": enable}
        response, data = await self.request("PATCH", url, json=body)
        return data

    # USER - APP SETTINGS - Text & Images

    async def enable_linked_image_display(self, enable: bool):
        """
        Enables or disables the display of images linked in chat.
        :param enable: Boolean indicating whether to enable or disable inline image display.
        :return: Response data after updating the setting.
        """
        url = f"{self.BASE_API_URL}/users/@me/settings"
        body = {"inline_embed_media": enable}
        response, data = await self.request("PATCH", url, json=body)
        return data

    async def enable_image_display(self, enable: bool):
        """
        Enables or disables the display of images directly uploaded to chat.
        :param enable: Boolean indicating whether to enable or disable inline attachment media display.
        :return: Response data after updating the setting.
        """
        url = f"{self.BASE_API_URL}/users/@me/settings"
        body = {"inline_attachment_media": enable}
        response, data = await self.request("PATCH", url, json=body)
        return data

    async def enable_link_preview(self, enable: bool):
        """
        Enables or disables link preview in chat messages.
        :param enable: Boolean indicating whether to enable or disable rendering of link embeds.
        :return: Response data after updating the setting.
        """
        url = f"{self.BASE_API_URL}/users/@me/settings"
        body = {"render_embeds": enable}
        response, data = await self.request("PATCH", url, json=body)
        return data

    async def enable_reaction_rendering(self, enable: bool):
        """
        Enables or disables the rendering of message reactions.
        :param enable: Boolean indicating whether to enable or disable rendering of reactions.
        :return: Response data after updating the setting.
        """
        url = f"{self.BASE_API_URL}/users/@me/settings"
        body = {"render_reactions": enable}
        response, data = await self.request("PATCH", url, json=body)
        return data

    async def enable_emoticon_conversion(self, enable: bool):
        """
        Enables or disables the conversion of emoticons to emojis.
        :param enable: Boolean indicating whether to enable or disable emoticon conversion.
        :return: Response data after updating the setting.
        """
        url = f"{self.BASE_API_URL}/users/@me/settings"
        body = {"convert_emoticons": enable}
        response, data = await self.request("PATCH", url, json=body)
        return data

    # USER - APP SETTINGS - Notifications

    async def set_afk_timeout(self, timeout_seconds: int):
        """
        Sets the AFK (Away From Keyboard) timeout duration.
        :param timeout_seconds: The duration in seconds for AFK timeout.
        :return: Response data after updating the setting.
        """
        url = f"{self.BASE_API_URL}/users/@me/settings"
        body = {"afk_timeout": timeout_seconds}
        response, data = await self.request("PATCH", url, json=body)
        return data

    # USER - APP SETTINGS - Language

    async def set_locale(self, locale: str):
        """
        Sets the user's language preference.
        :param locale: String representing the locale to set (e.g., 'en-US').
        :return: Response data after updating the setting.
        """
        url = f"{self.BASE_API_URL}/users/@me/settings"
        body = {"locale": locale}
        response, data = await self.request("PATCH", url, json=body)
        return data

    # USER - APP SETTINGS - Advanced

    async def enable_dev_mode(self, enable: bool):
        """
        Enables or disables Developer Mode in Discord settings.
        :param enable: Boolean indicating whether to enable or disable Developer Mode.
        :return: Response data after updating the setting.
        """
        url = f"{self.BASE_API_URL}/users/@me/settings"
        body = {"developer_mode": enable}
        response, data = await self.request("PATCH", url, json=body)
        return data

    async def activate_application_test_mode(self, application_id: str):
        """
        Activates test mode for a specific application.
        :param application_id: The ID of the application to activate test mode for.
        :return: Response data after activating test mode.
        """
        url = f"{self.BASE_API_URL}/applications/{application_id}/skus"
        response, data = await self.request("GET", url)
        return data

    async def get_application_data(self, application_id: str, with_guild: bool):
        """
        Retrieves data for a specific application.
        :param application_id: The ID of the application.
        :param with_guild: Boolean indicating whether to include guild information.
        :return: Application data.
        """
        url = f"{self.BASE_API_URL}/applications/{application_id}/public?with_guild={str(with_guild).lower()}"
        response, data = await self.request("GET", url)
        return data

    # USER - ACTIVITY SETTINGS

    async def enable_activity_display(self, enable: bool, timeout: int = None):
        """
        Enables or disables the display of current activity status.
        :param enable: Boolean indicating whether to show the current game/activity.
        :param timeout: Optional timeout parameter for the request.
        :return: Response data after updating the activity display setting.
        """
        url = f"{self.BASE_API_URL}/users/@me/settings"
        body = {"show_current_game": enable}
        response, data = await self.request("PATCH", url, json=body, timeout=timeout)
        return data

    # USER - OTHER SETTINGS - HypeSquad

    async def set_hypesquad(self, house: str):
        """
        Sets the HypeSquad house for the user.
        :param house: The HypeSquad house to join ('Bravery', 'Brilliance', 'Balance').
        :return: Response data after joining the HypeSquad house.
        """
        url = f"{self.BASE_API_URL}/hypesquad/online"
        house_ids = {"bravery": 1, "brilliance": 2, "balance": 3}
        body = {"house_id": house_ids.get(house.lower(), 1)}
        response, data = await self.request("POST", url, json=body)
        return data

    async def leave_hypesquad(self):
        """
        Leaves the HypeSquad.
        :return: Response data after leaving the HypeSquad.
        """
        url = f"{self.BASE_API_URL}/hypesquad/online"
        response, data = await self.request("DELETE", url)
        return data

    # USER - OTHER SETTINGS - Developer Options

    async def get_build_overrides(self):
        """
        Retrieves build override settings for the user.
        :return: Response data with build override settings.
        """
        url = "https://discord.com/__development/build_overrides"
        response, data = await self.request("GET", url)
        return data

    async def enable_source_maps(self, enable: bool):
        """
        Enables or disables source maps.
        :param enable: Boolean indicating whether to enable or disable source maps.
        :return: Response data after updating the setting.
        """
        url = "https://discord.com/__development/source_maps"
        method = "PUT" if enable else "DELETE"
        response, data = await self.request(method, url)
        return data

    # USER - OTHER SETTINGS - Notification Settings

    async def suppress_everyone_pings(self, guild_id: int | str, suppress: bool):
        """
        Suppresses or allows '@everyone' pings in a specific guild.
        :param guild_id: ID of the guild.
        :param suppress: Boolean indicating whether to suppress '@everyone' pings.
        :return: Response data after updating the setting.
        """
        url = f"{self.BASE_API_URL}/users/@me/guilds/{guild_id}/settings"
        body = {"suppress_everyone": suppress}
        response, data = await self.request("PATCH", url, json=body)
        return data

    async def suppress_role_mentions(self, guild_id: int | str, suppress: bool):
        """
        Suppresses or allows role mentions in a specific guild.
        :param guild_id: ID of the guild.
        :param suppress: Boolean indicating whether to suppress role mentions.
        :return: Response data after updating the setting.
        """
        url = f"{self.BASE_API_URL}/users/@me/guilds/{guild_id}/settings"
        body = {"suppress_roles": suppress}
        response, data = await self.request("PATCH", url, json=body)
        return data

    async def enable_mobile_push_notifications(self, guild_id: int | str, enable: bool):
        """
        Enables or disables mobile push notifications for a specific guild.
        :param guild_id: ID of the guild.
        :param enable: Boolean indicating whether to enable mobile push notifications.
        :return: Response data after updating the setting.
        """
        url = f"{self.BASE_API_URL}/users/@me/guilds/{guild_id}/settings"
        body = {"mobile_push": enable}
        response, data = await self.request("PATCH", url, json=body)
        return data

    async def set_channel_notification_overrides(self, guild_id: int | str, overrides: dict):
        """
        Sets channel-specific notification overrides for a guild.
        :param guild_id: ID of the guild.
        :param overrides: Dictionary of channel overrides.
        :return: Response data after updating the setting.
        """
        url = f"{self.BASE_API_URL}/users/@me/guilds/{guild_id}/settings"
        body = {"channel_overrides": overrides}
        response, data = await self.request("PATCH", url, json=body)
        return data

    async def set_message_notifications(self, guild_id: int | str, notifications: str):
        """
        Sets the message notification setting for a guild.
        :param guild_id: ID of the guild.
        :param notifications: Notification setting ('all messages', 'only mentions', 'nothing').
        :return: Response data after updating the setting.
        """
        url = f"{self.BASE_API_URL}/users/@me/guilds/{guild_id}/settings"
        notification_types = {"all messages": 0, "only mentions": 1, "nothing": 2}
        body = {"message_notifications": notification_types.get(notifications.lower(), 1)}
        response, data = await self.request("PATCH", url, json=body)
        return data

    async def mute_guild(self, guild_id: int | str, mute: bool, duration: int = None):
        """
        Mutes or unmutes a guild for a specified duration.
        :param guild_id: ID of the guild.
        :param mute: Boolean indicating whether to mute the guild.
        :param duration: Duration in minutes to mute the guild, None for indefinite.
        :return: Response data after updating the setting.
        """
        url = f"{self.BASE_API_URL}/users/@me/guilds/{guild_id}/settings"
        body = {"muted": mute}
        if mute and duration is not None:
            end_time = datetime.datetime.now(datetime.UTC) + datetime.timedelta(minutes=duration)
            body["mute_config"] = {"selected_time_window": duration, "end_time": end_time.isoformat()}
        response, data = await self.request("PATCH", url, json=body)
        return data

    async def mute_dm(self, dm_id: int | str, mute: bool, duration: int = None):
        """
        Mutes or unmutes a direct message channel for a specified duration.
        :param dm_id: ID of the direct message channel.
        :param mute: Boolean indicating whether to mute the DM.
        :param duration: Duration in minutes to mute the DM, None for indefinite.
        :return: Response data after updating the setting.
        """
        url = f"{self.BASE_API_URL}/users/@me/guilds/%40me/settings"
        data = {"muted": mute}
        if mute and duration is not None:
            end_time = datetime.datetime.now(datetime.UTC) + datetime.timedelta(minutes=duration)
            data["mute_config"] = {"selected_time_window": duration, "end_time": end_time.isoformat()}
        body = {"channel_overrides": {str(dm_id): data}}
        response, data = await self.request("PATCH", url, json=body)
        return data

    async def set_thread_notifications(self, thread_id: int | str, notifications: str):
        """
        Sets the notification setting for a specific thread.
        :param thread_id: ID of the thread.
        :param notifications: Notification setting ('all messages', 'only mentions', 'nothing').
        :return: Response data after updating the setting.
        """
        url = f"{self.BASE_API_URL}/channels/{thread_id}/thread-members/@me/settings"
        notification_types = {"all messages": 0, "only mentions": 1, "nothing": 2}
        flags = 1 << (notification_types.get(notifications.lower(), 1) + 1)
        body = {"flags": flags}
        response, data = await self.request("PATCH", url, json=body)
        return data

    async def get_report_menu(self):
        """
        Retrieves the report menu for the first direct message.
        :return: Response data with report menu options.
        """
        url = f"{self.BASE_API_URL}/reporting/menu/first_dm"
        response, data = await self.request("GET", url)
        return data

    async def report_spam(self, channel_id: int | str, message_id: int | str, report_type: str, guild_id: int | str,
                          version: str, variant: str, language: str):
        """
        Reports a message as spam.
        :param channel_id: ID of the channel where the message is located.
        :param message_id: ID of the message to report.
        :param report_type: Type of report.
        :param guild_id: ID of the guild, if applicable.
        :param version: Version information for the report.
        :param variant: Variant of the report.
        :param language: Language setting for the report.
        :return: Response data after submitting the report.
        """
        url = f"{self.BASE_API_URL}/reporting/{report_type}"
        body = {
            "id": generate_nonce(),
            "version": version,
            "variant": variant,
            "language": language,
            "breadcrumbs": [7],
            "elements": {},
            "name": report_type,
            "channel_id": channel_id,
            "message_id": message_id,
        }
        if report_type in ('guild_directory_entry', 'stage_channel', 'guild'):
            body["guild_id"] = guild_id
        response, data = await self.request("POST", url, json=body)
        return data

    async def get_handoff_token(self, key: str):
        """
        Retrieves a handoff token.
        :param key: The key for which the handoff token is requested.
        :return: Response data with the handoff token.
        """
        url = f"{self.BASE_API_URL}/auth/handoff"
        body = {"key": key}
        response, data = await self.request("POST", url, json=body)
        return data

    async def invite_to_call(self, channel_id: int | str, user_ids: list):
        """
        Invites users to a call in a specific channel.
        :param channel_id: ID of the channel where the call is hosted.
        :param user_ids: List of user IDs to invite to the call.
        :return: Response data after sending the call invites.
        """
        url = f"{self.BASE_API_URL}/channels/{channel_id}/call/ring"
        body = {"recipients": user_ids}
        response, data = await self.request("POST", url, json=body)
        return data

    async def decline_call(self, channel_id: int | str):
        """
        Declines a call in a specific channel.
        :param channel_id: ID of the channel where the call is hosted.
        :return: Response data after declining the call.
        """
        url = f"{self.BASE_API_URL}/channels/{channel_id}/call/stop-ringing"
        response, data = await self.request("POST", url)
        return data

    # USER - Logout

    async def logout(self, provider: str, voip_provider: str):
        """
        Logs the user out of Discord.
        :param provider: The authentication provider.
        :param voip_provider: The VOIP provider.
        :return: Response data after logging out.
        """
        url = f"{self.BASE_API_URL}/auth/logout"
        body = {"provider": provider, "voip_provider": voip_provider}
        response, data = await self.request("POST", url, json=body)
        return data

