import sys, asyncio
from itertools import cycle
from pathlib import Path
from curl_cffi import requests

from tqdm.asyncio import tqdm

from better_automation.twitter import TwitterAccount, TwitterClient, TwitterAccountStatus
from better_automation.twitter.errors import HTTPException as TwitterException
from better_automation.utils import (
    load_lines,
    write_lines,
    bounded_gather,
)

from examples.common import set_windows_event_loop_policy, PROXY

set_windows_event_loop_policy()

TwitterAccountWithAdditionalData = tuple[str, TwitterAccount]
SortedAccounts = dict[TwitterAccountStatus: TwitterAccountWithAdditionalData]

INPUT_OUTPUT_DIR = Path('input-output')
INPUT_OUTPUT_DIR.mkdir(exist_ok=True)
MAX_TASKS = 100
SEPARATOR = ":"


def sort_accounts(
        accounts: list[TwitterAccountWithAdditionalData]
) -> SortedAccounts:
    status_to_account_with_additional_data = {status: list() for status in TwitterAccountStatus}
    for additional_data, account in accounts:
        status_to_account_with_additional_data[account.status].append((additional_data, account))
    return status_to_account_with_additional_data


def save_sorted_accounts_with_additional_data(sorted_accounts: dict[TwitterAccountStatus: (str, TwitterAccount)]):
    for status, accounts_with_additional_data in sorted_accounts.items():
        filepath = INPUT_OUTPUT_DIR / f'{status}.txt'
        lines = [additional_data for additional_data, account in accounts_with_additional_data]
        write_lines(filepath, lines)


def load_accounts_with_additional_data() -> list[TwitterAccountWithAdditionalData]:
    accounts = list()
    for file in INPUT_OUTPUT_DIR.iterdir():
        if file.is_file():
            status = file.stem
            for additional_data in load_lines(file):
                auth_token = additional_data.split(SEPARATOR)[-1]
                account = TwitterAccount(auth_token)
                account.status = status
                accounts.append((additional_data, account))
    return accounts


def print_statistic(sorted_accounts: SortedAccounts):
    for status, accounts_with_additional_data in sorted_accounts.items():
        print(f"{status}: {len(accounts_with_additional_data)}")


async def establish_account_status(account: TwitterAccount, proxy: str = None):
    async with TwitterClient(account, proxy=proxy, verify=False) as twitter:
        try:
            await twitter.follow(44196397)  # Elon Musk ID
        except TwitterException:
            pass
        except requests.errors.RequestsError:
            pass

    tqdm.write(f"{account} {account.status}")


async def check_accounts(
        accounts: list[TwitterAccountWithAdditionalData],
        proxies: list[str],
):
    sorted_accounts = sort_accounts(accounts)
    print_statistic(sorted_accounts)

    proxies_cycle = cycle(proxies)  # Создаем итератор, который будет циклически проходить по прокси

    tasks = []
    for line, account in accounts:
        if account.status == TwitterAccountStatus.UNKNOWN:
            proxy = next(proxies_cycle)  # Получаем следующий прокси из итератора
            tasks.append(establish_account_status(account, proxy=proxy))
    try:
        await bounded_gather(*tasks, max_tasks=MAX_TASKS, file=sys.stdout)
    finally:
        sorted_accounts = sort_accounts(accounts)
        save_sorted_accounts_with_additional_data(sorted_accounts)
        print_statistic(sorted_accounts)


if __name__ == '__main__':
    accounts = load_accounts_with_additional_data()
    if not accounts:
        accounts_filepath = INPUT_OUTPUT_DIR / f"{TwitterAccountStatus.UNKNOWN}.txt"
        accounts_filepath.touch()
        print(f"Внесите аккаунты в файл по пути {accounts_filepath}")
        quit()

    proxies = load_lines("proxies.txt")
    asyncio.run(check_accounts(accounts, proxies))
