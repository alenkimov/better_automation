import asyncio
from itertools import cycle
from pathlib import Path

import twitter.utils
from better_proxy import Proxy
from better_automation import discord as better_discord

INPUT_OUTPUT_DIR = Path("input-output")
INPUT_OUTPUT_DIR.mkdir(exist_ok=True)

PROXIES_TXT = INPUT_OUTPUT_DIR / "PROXIES.txt"
DISCORDS_TXT = INPUT_OUTPUT_DIR / f"DISCORDS.txt"
[filepath.touch() for filepath in (PROXIES_TXT, DISCORDS_TXT)]

INVITE = "zenlesszonezero"


class GuildJoiner(better_discord.Client):
    def __init__(self, invite: str, **options):
        super().__init__(**options)
        self.invite = invite

    async def on_ready(self):
        print(f'[@{self.user}] Logged on')
        if not self.user.phone:
            print(f"[@{self.user}] No phone number!")
            await self.close()
            return

        invite = await self.accept_invite(self.invite)
        guild_info = f"{invite.guild.name} guild ({invite.approximate_member_count} members)"
        print(f"[@{self.user}] {guild_info}: joined guild")
        await self.agree_guild_rules(invite)
        print(f"[@{self.user}] {guild_info}: accepted rules")

        await self.close()
        return


async def join_guild(
        proxies: list[Proxy],
        discord_tokens: list[str],
        invite: str,
):
    if not proxies:
        proxies = (None, )

    for proxy, discord_token in zip(cycle(proxies), discord_tokens):
        joiner = GuildJoiner(invite, proxy=proxy)
        await joiner.start(discord_token)


if __name__ == '__main__':
    proxies = Proxy.from_file(PROXIES_TXT)
    print(f"Прокси: {len(proxies)}")
    if not proxies:
        print(f"(Необязательно) Внесите прокси в любом формате "
              f"\n\tв файл по пути {PROXIES_TXT}")

    discord_tokens = twitter.utils.load_lines(DISCORDS_TXT)
    if not discord_tokens:
        print(f"Внесите Discord токены"
              f"\n\tв файл по пути {DISCORDS_TXT}")
        quit()

    asyncio.run(join_guild(proxies, discord_tokens, INVITE))
