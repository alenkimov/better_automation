import asyncio
from urllib.parse import urlparse

import discord
from discord import CaptchaRequired
from discord.http import Route
from discord.types.snowflake import Snowflake
from python3_capsolver.hcaptcha import HCaptcha, HCaptchaTypeEnm
from better_proxy import Proxy

from .account import Account


class Client(discord.Client):
    """
    - Принимает прокси в формате URL и better-proxy.
    - Метод agree_guild_rules для принятия правил сервера.
    - Обработка капчи с CapSolver.
    """
    def __init__(self, capsolver_api_key: str | None,  **options):
        proxy = options.pop('proxy', None)
        if isinstance(proxy, Proxy):
            options['proxy'] = proxy.as_url

        super().__init__(**options)
        self.capsolver_api_key = capsolver_api_key
        self.account: Account | None = None

    async def handle_captcha(self, exception: CaptchaRequired, /) -> str:
        if not self.capsolver_api_key:
            await super().handle_captcha(exception)

        hcaptcha = {
            "api_key": self.capsolver_api_key,
            "websiteURL": "https://discord.com/channels/@me",
            "websiteKey": exception.sitekey,
            "enterprisePayload": {
                "rqdata": exception.rqdata
            },
            "userAgent": self.http.user_agent,
        }
        if self.http.proxy:
            hcaptcha["captcha_type"] = HCaptchaTypeEnm.HCaptchaTask
            parsed_proxy = urlparse(self.http.proxy)
            hcaptcha["proxy"] = f"{parsed_proxy.scheme}:{parsed_proxy.hostname}:{parsed_proxy.port}:{parsed_proxy.username}:{parsed_proxy.password}"
        else:
            hcaptcha["captcha_type"] = HCaptchaTypeEnm.HCaptchaTaskProxyless

        solution = await HCaptcha(**hcaptcha).aio_captcha_handler()
        token = solution.solution["token"]
        return token

    async def on_ready(self):
        self.account.status = "GOOD"
        self.account.id = self.user.id
        self.account.email = self.user.email
        self.account.name = self.user.display_name
        self.account.username = self.user.name
        self.account.bio = self.user.bio
        self.account.phone = self.user.phone

    async def start_with_discord_account(self, account: Account, *, reconnect: bool = True):
        self.account = account
        max_retries = 3  # Set the maximum number of retries
        for attempt in range(max_retries):
            try:
                await super().start(self.account.auth_token, reconnect=reconnect)
                break  # If successful, exit the loop
            except ValueError as e:
                if "is not a valid HTTPStatus" in str(e):
                    if attempt < max_retries - 1:
                        await asyncio.sleep(1)  # Wait before retrying
                        continue  # Retry the request
                    else:
                        raise  # Re-raise the exception after all retries have failed
                else:
                    raise  # Re-raise the exception if it's not related to HTTPStatus
            except discord.errors.LoginFailure:
                self.account.status = "BAD_TOKEN"

    async def _request_guild_rules_form(
            self,
            invite_code: str,
            guild_id: Snowflake,
    ):
        params = {
            "with_guild": "false",
            "invite_code": invite_code,
        }
        route = Route('GET', '/guilds/{guild_id}/member-verification', guild_id=guild_id)
        return await self.http.request(route, params=params)

    async def _agree_guild_rules(
            self,
            guild_id: Snowflake,
            rules_form: dict,
    ):
        form_fields = rules_form["form_fields"][0].copy()
        form_fields["response"] = True
        payload = {
            "version": rules_form["version"],
            "form_fields": [form_fields],
        }
        route = Route('PUT', '/guilds/{guild_id}/requests/@me', guild_id=guild_id)
        return await self.http.request(route, json=payload)

    async def agree_guild_rules(
            self,
            url: str,
            guild_id: Snowflake,
    ):
        invite = discord.utils.resolve_invite(url)
        try:
            rules_form = await self._request_guild_rules_form(invite.code, guild_id)
            return await self._agree_guild_rules(guild_id, rules_form)
        except discord.errors.HTTPException as exc:
            if exc.code != 150009:
                raise
