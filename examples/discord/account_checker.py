"""
Скрипт для установки статуса Discord аккаунтов.

pip install better-automation better-proxy
"""

import asyncio
import sys
from itertools import cycle
from pathlib import Path
from typing import Iterable, Sequence
from contextlib import asynccontextmanager
from typing import AsyncContextManager

from curl_cffi import requests
from tqdm.asyncio import tqdm

from better_automation.legacy.discord import DiscordAccount, DiscordClient
from better_automation.legacy.discord.account import DiscordAccountStatus
from better_automation.legacy.discord.errors import DiscordException
from better_automation.utils import gather
from better_proxy import Proxy

SortedDiscordAccounts = dict[DiscordAccountStatus: list[DiscordAccount]]

INPUT_OUTPUT_DIR = Path("input-output")
INPUT_OUTPUT_DIR.mkdir(exist_ok=True)

PROXIES_TXT = INPUT_OUTPUT_DIR / "PROXIES.txt"
PROXIES_TXT.touch()

UNKNOWN_TXT = INPUT_OUTPUT_DIR / f"{DiscordAccountStatus.UNKNOWN}.txt"
ACCOUNTS_TXT_FILES = [INPUT_OUTPUT_DIR / f"{status}.txt" for status in DiscordAccountStatus.__members__]
[filepath.touch() for filepath in ACCOUNTS_TXT_FILES]

MAX_TASKS = 100
SEPARATOR = ":"
FIELDS = ("auth_token", "password", "email")


@asynccontextmanager
async def discord_client(
        account: DiscordAccount,
        proxy: Proxy = None,
        verify: bool = False,
) -> AsyncContextManager[DiscordClient]:
    async with DiscordClient(account, proxy=proxy.as_url if proxy else None, verify=verify) as discord:
        yield discord


def load_accounts_with_statuses(
        dir_path: str | Path,
        separator: str,
        fields: Sequence[str],
) -> list[DiscordAccount]:
    """
    Сканирует папку на текстовые файлы с названиями статусов (DiscordAccountStatus)
    и возвращает список аккаунтов с установленными статусами аккаунтов согласно названиям файлам.
    """
    accounts = list()
    for file in Path(dir_path).iterdir():
        if file.is_file() and file.stem in DiscordAccountStatus.__members__:
            status = file.stem
            for account in DiscordAccount.from_file(file, separator=separator, fields=fields):
                account.status = status
                accounts.append(account)
    return accounts


def sort_accounts(accounts: Iterable[DiscordAccount]) -> SortedDiscordAccounts:
    # Don't use defaultdict here
    status_to_account = {status: [] for status in DiscordAccountStatus}
    for account in accounts:
        status_to_account[account.status].append(account)
    return status_to_account


def save_sorted_accounts(
        dir_path: str | Path,
        sorted_accounts: SortedDiscordAccounts,
        separator: str,
        fields: Sequence[str],
):
    for status, accounts in sorted_accounts.items():
        filepath = Path(dir_path) / f"{status}.txt"
        DiscordAccount.to_file(filepath, accounts, separator=separator, fields=fields)


def print_sorted_accounts_count(sorted_accounts: SortedDiscordAccounts):
    for status, accounts in sorted_accounts.items():
        print(f"{status}: {len(accounts)}")


async def establish_account_status(account: DiscordAccount, proxy: Proxy = None):
    async with discord_client(account, proxy) as discord:
        discord: DiscordClient
        try:
            await discord.request_user_data()
            await discord.request_guilds()
        except (DiscordException, requests.errors.RequestsError):
            pass
    message = f"{account} {account.status}"
    if account.is_spammer: message += "(SPAMMER)"
    if account.is_quarantined: message += "(QUARANTINED)"
    tqdm.write(message)


async def check_accounts(
        proxies: Iterable[Proxy],
        accounts: Iterable[DiscordAccount],
        output_dir: str | Path,
        separator: str,
        fields: Sequence[str],
        max_tasks: int = 100,
):

    sorted_accounts = sort_accounts(accounts)
    print_sorted_accounts_count(sorted_accounts)

    if not proxies:
        proxies = [None]

    proxy_to_account_list = list(zip(cycle(proxies), accounts))
    tasks = [establish_account_status(account, proxy)
             for proxy, account in proxy_to_account_list
             if account.status == DiscordAccountStatus.UNKNOWN]

    if not tasks: return

    try:
        await gather(*tasks, max_tasks=max_tasks, file=sys.stdout)
    finally:
        sorted_accounts = sort_accounts(accounts)
        save_sorted_accounts(output_dir, sorted_accounts, separator, fields)
        print_sorted_accounts_count(sorted_accounts)


if __name__ == '__main__':
    proxies = Proxy.from_file(PROXIES_TXT)
    print(f"Прокси: {len(proxies)}")
    if not proxies:
        print(f"(Необязательно) Внесите прокси в любом формате "
              f"\n\tв файл по пути {PROXIES_TXT}")

    accounts = load_accounts_with_statuses(INPUT_OUTPUT_DIR, SEPARATOR, FIELDS)
    if not accounts:
        print(f"Внесите аккаунты в формате {SEPARATOR.join(FIELDS)}"
              f" (auth_token - обязательный параметр, остальные - нет)"
              f"\n\tв файл по пути {UNKNOWN_TXT}")
        quit()

    asyncio.run(check_accounts(proxies, accounts, INPUT_OUTPUT_DIR, SEPARATOR, FIELDS, MAX_TASKS))
