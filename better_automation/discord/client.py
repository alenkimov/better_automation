import discord
from discord.http import Route


class Client(discord.Client):
    """
    - Принимает прокси в формате URL и better-proxy.
    - Метод agree_guild_rules для принятия правил сервера.
    """
    def __init__(self, **options):
        if 'proxy' in options and options['proxy'] is not None:
            # Если это better-proxy, то str() преобразует его к формату url
            options['proxy'] = str(options['proxy'])

        super().__init__(**options)

    async def _request_guild_rules_form(self, invite: discord.Invite):
        params = {
            "with_guild": "false",
            "invite_code": invite.code,
        }
        route = Route('GET', '/guilds/{guild_id}/member-verification', guild_id=invite.guild.id)
        return await self.http.request(route, params=params)

    async def _agree_guild_rules(
            self,
            guild_id: int,
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
