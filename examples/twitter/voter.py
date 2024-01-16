"""
Скрипт для массового голосования.

pip install better-automation better-proxy
"""

import asyncio
from contextlib import asynccontextmanager
from typing import AsyncContextManager
from itertools import cycle
from pathlib import Path
from typing import Iterable

from better_automation.twitter import TwitterAccount, TwitterClient, TwitterAccountStatus
from better_proxy import Proxy

TwitterAccountWithAdditionalData = tuple[str, TwitterAccount]
SortedAccounts = dict[TwitterAccountStatus: TwitterAccountWithAdditionalData]

INPUT_OUTPUT_DIR = Path("input-output")
INPUT_OUTPUT_DIR.mkdir(exist_ok=True)

PROXIES_TXT = INPUT_OUTPUT_DIR / "PROXIES.txt"
ACCOUNTS_TXT = INPUT_OUTPUT_DIR / f"{TwitterAccountStatus.GOOD}.txt"
[filepath.touch() for filepath in (PROXIES_TXT, ACCOUNTS_TXT)]

MAX_TASKS = 100
SEPARATOR = ":"
FIELDS = ("auth_token", "password", "email", "username", "ct0")

# Для того чтобы накрутить голоса, нужно достать параметры tweet_id и card_id.
# Их можно найти в параметрах запросов на странице твита с голосованием.
TWEET_ID = 1701624723933905280
CARD_ID = 1701624722256236544
CHOICE_NUMBER = 1


@asynccontextmanager
async def twitter_client(
        account: TwitterAccount,
        proxy: Proxy = None,
        verify: bool = False,
) -> AsyncContextManager[TwitterClient]:
    async with TwitterClient(account, proxy=proxy.as_url if proxy else None, verify=verify) as twitter:
        yield twitter


async def vote(
        proxies: Iterable[Proxy],
        accounts: Iterable[TwitterAccount],
        tweet_id: int,
        card_id: int,
        choice_number: int,
):

    if not proxies:
        proxies = [None]

    proxy_to_account_list = list(zip(cycle(proxies), accounts))

    for proxy, account in proxy_to_account_list:
        async with twitter_client(account, proxy) as twitter:
            vote_data = await twitter.vote(tweet_id, card_id, choice_number)
            votes_count = vote_data["card"]["binding_values"]["choice1_count"]["string_value"]
            print(f"Votes: {votes_count}")


if __name__ == '__main__':
    proxies = Proxy.from_file(PROXIES_TXT)
    print(f"Прокси: {len(proxies)}")
    if not proxies:
        print(f"(Необязательно) Внесите прокси в любом формате "
              f"\n\tв файл по пути {PROXIES_TXT}")

    accounts = TwitterAccount.from_file(ACCOUNTS_TXT)
    if not accounts:
        print(f"Внесите аккаунты в формате {SEPARATOR.join(FIELDS)}"
              f" (auth_token - обязательный параметр, остальные - нет)"
              f"\n\tв файл по пути {ACCOUNTS_TXT}")
        quit()

    asyncio.run(vote(proxies, accounts, TWEET_ID, CARD_ID, CHOICE_NUMBER))
