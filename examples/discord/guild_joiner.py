"""
Скрипт для массового захода на сервер.
"""

import asyncio
from itertools import cycle
from pathlib import Path
import logging

import discord
from better_proxy import Proxy
from better_automation import discord as better_discord

INPUT_OUTPUT_DIR = Path("input-output")
INPUT_OUTPUT_DIR.mkdir(exist_ok=True)

PROXIES_TXT = INPUT_OUTPUT_DIR / "PROXIES.txt"
ACCOUNTS_TXT = INPUT_OUTPUT_DIR / f"{better_discord.AccountStatus.GOOD}.txt"
[filepath.touch() for filepath in (PROXIES_TXT, ACCOUNTS_TXT)]

MAX_TASKS = 100
SEPARATOR = ":"
FIELDS = ("auth_token", )

# INVITE = "https://discord.gg/tabinft"
INVITE = "tabinft"

discord.utils.setup_logging(level=logging.INFO)


class GuildJoiner(better_discord.Client):
    def __init__(self, invite: str, **options):
        super().__init__(**options)
        self.invite_url = invite

    async def on_ready(self):
        await super().on_ready()

        if not self.account.phone:
            print(f"{self.account} No phone number")
            await self.close()
            return

        print(f'Logged on as @{self.user}')

        invite = await self.accept_invite(self.invite_url)
        print(f"Сервер {invite.guild.name} ({invite.approximate_member_count} members)")
        await self.agree_guild_rules(invite)

        await self.close()
        return


async def join_guild(
        proxies: list[Proxy],
        accounts: list[better_discord.Account],
        invite: str,
):
    if not proxies:
        proxies = (None, )

    for proxy, account in zip(cycle(proxies), accounts):
        joiner = GuildJoiner(invite, proxy=proxy)
        await joiner.start_with_discord_account(account)


if __name__ == '__main__':
    proxies = Proxy.from_file(PROXIES_TXT)
    print(f"Прокси: {len(proxies)}")
    if not proxies:
        print(f"(Необязательно) Внесите прокси в любом формате "
              f"\n\tв файл по пути {PROXIES_TXT}")

    accounts = better_discord.load_accounts_from_file(ACCOUNTS_TXT, separator=SEPARATOR, fields=FIELDS)
    if not accounts:
        print(f"Внесите аккаунты в формате {SEPARATOR.join(FIELDS)}"
              f" (auth_token - обязательный параметр, остальные - нет)"
              f"\n\tв файл по пути {ACCOUNTS_TXT}")
        quit()

    asyncio.run(join_guild(proxies, accounts, INVITE))
