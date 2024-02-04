"""
Скрипт для массового захода на сервер.
"""

import asyncio
from itertools import cycle
from pathlib import Path
from typing import Iterable

from better_automation.legacy.discord import DiscordAccount, DiscordClient, DiscordAccountStatus, to_invite_code
from better_automation.legacy.discord.errors import DiscordException
from better_automation.legacy.discord.account import from_file as discord_from_file
from better_proxy import Proxy

INPUT_OUTPUT_DIR = Path("input-output")
INPUT_OUTPUT_DIR.mkdir(exist_ok=True)

PROXIES_TXT = INPUT_OUTPUT_DIR / "PROXIES.txt"
ACCOUNTS_TXT = INPUT_OUTPUT_DIR / f"{DiscordAccountStatus.GOOD}.txt"
[filepath.touch() for filepath in (PROXIES_TXT, ACCOUNTS_TXT)]

MAX_TASKS = 100
SEPARATOR = ":"
FIELDS = ("auth_token", "password", "email")

INVITE_CODE_OR_URL = "tabinft"


async def join_guild(
        proxies: Iterable[Proxy],
        accounts: Iterable[DiscordAccount],
        invite_code_or_url: str,
):
    invite_code = to_invite_code(invite_code_or_url)

    if not proxies:
        proxies = [None]

    proxy_to_account_list = list(zip(cycle(proxies), accounts))

    for proxy, account in proxy_to_account_list:
        async with DiscordClient(account, proxy=proxy) as discord:
            try:
                invite_data = await discord.request_invite_data(invite_code)
                print(f"{proxy} {account} (account status: {account.status})"
                      f" Сервер {invite_data['guild']['name']} ({invite_data['approximate_member_count']} members)")
            except DiscordException as e:
                print(f"{proxy} {account} (account status: {account.status})"
                      f" Не удалось запросить данные о сервере: {e}")

            guild_data = None
            try:
                guild_data = await discord.join_guild_with_invite_data(invite_data)
                print(f"{proxy} {account} (account status: {account.status})"
                      f" Успешно зашел на сервер")
            except DiscordException as e:
                print(f"{proxy} {account} (account status: {account.status})"
                      f" Не удалось зайти на сервер: {e}")

            if guild_data:
                try:
                    await discord.agree_guild_rules_with_invite_data(invite_data)
                    print(f"{proxy} {account} (account status: {account.status})"
                          f" Успешно согласился с правилами сервера")
                except DiscordException as e:
                    print(f"{proxy} {account} (account status: {account.status})"
                          f" Не удалось согласиться с правилами сервера: {e}")


if __name__ == '__main__':
    proxies = Proxy.from_file(PROXIES_TXT)
    print(f"Прокси: {len(proxies)}")
    if not proxies:
        print(f"(Необязательно) Внесите прокси в любом формате "
              f"\n\tв файл по пути {PROXIES_TXT}")

    accounts = discord_from_file(ACCOUNTS_TXT, separator=SEPARATOR, fields=FIELDS)
    if not accounts:
        print(f"Внесите аккаунты в формате {SEPARATOR.join(FIELDS)}"
              f" (auth_token - обязательный параметр, остальные - нет)"
              f"\n\tв файл по пути {ACCOUNTS_TXT}")
        quit()

    asyncio.run(join_guild(proxies, accounts, INVITE_CODE_OR_URL))
