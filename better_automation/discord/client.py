import asyncio

import discord
from discord.http import Route
from discord.types.snowflake import Snowflake
from better_proxy import Proxy

from .account import Account


class Client(discord.Client):
    """
    - Принимает прокси в формате URL и better-proxy.
    - Метод agree_guild_rules для принятия правил сервера.
    """
    def __init__(self, **options):
        proxy = options.pop('proxy', None)
        if isinstance(proxy, Proxy):
            options['proxy'] = proxy.as_url

        super().__init__(**options)
        self.account: Account | None = None

    async def on_ready(self):
        if self.account:
            self.account.status = "GOOD"
            self.account.id = self.user.id
            self.account.email = self.user.email
            self.account.name = self.user.display_name
            self.account.username = self.user.name
            self.account.bio = self.user.bio
            self.account.phone = self.user.phone
            self.account.flags = self.user._flags

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

    async def _request_guild_rules_form(self, invite: discord.Invite):
        params = {
            "with_guild": "false",
            "invite_code": invite.code,
        }
        route = Route('GET', '/guilds/{guild_id}/member-verification', guild_id=invite.guild.id)
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

    async def agree_guild_rules(self, url: str | discord.Invite):
        state = self._connection
        resolved = discord.utils.resolve_invite(url)

        data = await state.http.get_invite(
            resolved.code,
            with_counts=True,
            input_value=resolved.code if isinstance(url, discord.Invite) else url,
        )
        if isinstance(url, discord.Invite):
            invite = url
        else:
            invite = discord.Invite.from_incomplete(state=state, data=data)

        try:
            rules_form = await self._request_guild_rules_form(invite)
            return await self._agree_guild_rules(invite.guild.id, rules_form)
        except discord.errors.HTTPException as exc:
            if exc.code != 150009:
                raise
