import asyncio
from typing import Iterable

from better_automation.twitter import TwitterAccount, TwitterClient

from examples.common import set_windows_event_loop_policy, PROXY

set_windows_event_loop_policy()

ACCOUNTS = TwitterAccount.from_file("twitters.txt")

# Для того чтобы накрутить голоса, нужно достать параметры tweet_id и card_id.
# Их можно найти в параметрах запросов на странице твита с голосованием.
TWEET_ID = 1701624723933905280
CARD_ID = 1701624722256236544
CHOICE_NUMBER = 1


async def vote(
        accounts: Iterable[TwitterAccount],
        tweet_id: int,
        card_id: int,
        choice_number: int,
):
    for account in accounts:
        async with TwitterClient(account) as twitter:
            response_json = await twitter.vote(tweet_id, card_id, choice_number)
            votes_count = response_json["card"]["binding_values"]["choice1_count"]["string_value"]
            print(f"Votes: {votes_count}")


if __name__ == '__main__':
    asyncio.run(vote(ACCOUNTS, TWEET_ID, CARD_ID, CHOICE_NUMBER))
