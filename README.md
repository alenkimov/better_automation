# Better Site Automation
- Unofficial Twitter and Discord API
- ProxyIMAPClient

[![Telegram channel](https://img.shields.io/endpoint?url=https://runkit.io/damiankrawczyk/telegram-badge/branches/master?url=https://t.me/cum_insider)](https://t.me/cum_insider)
[![PyPI version info](https://img.shields.io/pypi/v/better-automation.svg)](https://pypi.python.org/pypi/better-automation)
[![PyPI supported Python versions](https://img.shields.io/pypi/pyversions/better-automation.svg)](https://pypi.python.org/pypi/better-automation)


```bash
pip install better-automation
```


More libraries of the family:
- [better-web3](https://github.com/alenkimov/better_web3)
- [better-proxy](https://github.com/alenkimov/better_proxy)


## Твиттер аккаунт
Аккаунт представляет собой контейнер для следующих данных:
- Токены авторизации: auth_token и x-csrf-token (ct0)
- Информация о пользователе: ID, username, дата регистрации и другая информация

Аккаунт можно создать из auth_token'а, cookies в JSON или base64:
```python
from better_automation.twitter import Account as TwitterAccount

account = TwitterAccount("auth_token")
account = TwitterAccount.from_cookies("JSON cookies")
account = TwitterAccount.from_cookies("base64 cookies", base64=True)
```

Аккаунты можно загрузить напрямую из файла:
```python
from better_automation.twitter import Account as TwitterAccount

accounts = TwitterAccount.from_file("twitter_auth_tokens.txt")
accounts = TwitterAccount.from_file("twitter_json_cookies.txt", cookies=True)
accounts = TwitterAccount.from_file("twitter_base64_cookies.txt", cookies=True, base64=True)
```

## Сессия и Твиттер клиент
Для взаимодействия с Твиттером сперва нужно создать сессию и соединить ее вместе с аккаунтом:
```python
import aiohttp

from better_automation.twitter import (
    Account as TwitterAccount,
    Client as TwitterClient,
)

async def main():
    async with aiohttp.ClientSession() as session:
        twitter = TwitterClient(TwitterAccount("auth_token"), session)
        ...
```

Вот так можно создать сессию с прокси:
```python
from better_automation.utils import proxy_session

PROXY = "http://login:password@host:port"

async def main():
    # proxy_session также принимает необязательный параметр user_agent
    # По умолчанию user_agent случаен
    async with proxy_session(PROXY) as session:
        response = session.get("https://ipapi.co/json")
        response_json = await response.json()
        print(f"{response_json['ip']} {response_json['country_name']}")
```

## Пример работы: установление статуса аккаунта (проверка на бан)
Вот так можно установить статус аккаунтов, выявив заблокированные аккаунты:
```python
import asyncio
from pathlib import Path
from collections import defaultdict

from better_automation.twitter.errors import HTTPException as TwitterException
from better_automation.utils import proxy_session, write_lines, load_lines
from better_automation.twitter import (
    Account as TwitterAccount,
    Client as TwitterClient,
)

PROXY = "http://login:password@host:port"

# Помимо токенов в файле с аккаунтами содержится и другая информация,
# поэтому мы не можем использовать TwitterAccount.from_file()
ACCOUNTS_TXT = Path('twitters.txt')

OUTPUT_DIR = Path('output')
OUTPUT_DIR.mkdir(exist_ok=True)
ELON_MUSK_ID = 44196397


async def check_accounts():
    checked = defaultdict(list)

    for line in load_lines(ACCOUNTS_TXT):
        auth_token = line.split(':')[-1]
        account = TwitterAccount(auth_token)

        async with proxy_session(PROXY) as session:
            twitter = TwitterClient(account, session)

            try:
                await twitter.follow(ELON_MUSK_ID)
            except TwitterException:
                pass

            print(f"{account} {account.status.value}")
            checked[account.status].append(line)

    for status, lines in checked.items():
        filepath = OUTPUT_DIR / f'{status.value}.txt'
        filepath.touch()
        write_lines(filepath, lines)


if __name__ == '__main__':
    asyncio.run(check_accounts())
```

## Пример работы: накрутка голосов
Для того чтобы повлиять на голосование, нужно достать параметры tweet_id и card_id.
Их можно найти в параметрах запросов на странице твита с голосованием.
Далее их нужно передать методу _vote():
```python
import asyncio

from better_automation.utils import proxy_session
from better_automation.twitter import (
    Account as TwitterAccount,
    Client as TwitterClient,
)

PROXY = "http://login:password@host:port"
ACCOUNTS = TwitterAccount.from_file("auth_tokens.txt")


async def vote(accounts):
    for account in accounts:
        async with proxy_session(PROXY) as session:
            twitter = TwitterClient(account, session)
            data = await twitter._vote(1701624723933905280, 1701624722256236544, 1)
            votes_count = data['card']['binding_values']['choice1_count']['string_value']
            print(f"Votes: {votes_count}")


if __name__ == '__main__':
    asyncio.run(vote(ACCOUNTS))
```

## Пример работы: прочие методы

```python
from better_automation.twitter import (
    Account as TwitterAccount,
    Client as TwitterClient,
    errors as twitter_errors,
)
from better_automation.utils import proxy_session


async def twitter_demo():
    account = TwitterAccount("auth_token")
    
    async with proxy_session() as session:
        twitter = TwitterClient(account, session)

        try:
            # Запрашиваем информацию о пользователе
            await twitter.request_user_data()
            print(f"[{account.short_auth_token}] {account.data}")
            print(f"Аккаунт создан: {account.data.created_at}")
            print(f"Всего подписчиков: {account.data.followers_count}")

            # Смена имени и год рождения (год рождения нужно менять обязательно)
            print(f"Имя и дата рождения установлены: {await twitter.update_profile(1, 1, 2002, name='Hitori Gotoh')}")

            # Выражение любви через твит
            tweet_id = await twitter.tweet("I love YOU! !!!!1")
            print(f"Любовь выражена! Tweet id: {tweet_id}")

            # Лайк
            print(f"Tweet {tweet_id} is liked: {await twitter.like(tweet_id)}")

            # Репост (ретвит)
            print(f"Tweet {tweet_id} is retweeted. Tweet id: {await twitter.repost(tweet_id)}")

            # Коммент (реплай)
            print(f"Tweet {tweet_id} is replied. Reply id: {await twitter.reply(tweet_id, 'tem razão')}")

            bind_data = {
                'response_type': 'code',
                'client_id': 'ZXh0SU5iS1pwTE5xclJtaVNNSjk6MTpjaQ',
                'redirect_uri': 'https://www.memecoin.org/farming',
                'scope': 'users.read tweet.read offline.access',
                'state': 'state',
                'code_challenge': 'challenge',
                'code_challenge_method': 'plain'
            }

            # Привязка к сайту \ приложению
            bind_code = await twitter.bind_app(**bind_data)
            print(f"Bind code: {bind_code}")

            # Запрашиваем информацию об Илоне Маске
            elonmusk = await twitter.request_user_data("@elonmusk")

            # Подписываемся на Илона Маска
            print(f"@{elonmusk.username} is followed: {await twitter.follow(elonmusk.id)}")

            # Отписываемся от Илона Маска
            print(f"@{elonmusk.username} is unfollowed: {await twitter.unfollow(elonmusk.id)}")

            tweet_url = 'https://twitter.com/CreamIce_Cone/status/1691735090529976489'
            # Цитата (Quote tweet)
            quote_tweet_id = await twitter.quote(tweet_url, 'oh...')
            print(f"Quoted! Tweet id: {quote_tweet_id}")

            # Запрашиваем первых трех подписчиков
            # (Параметр count по каким-то причинам работает некорректно)
            followers = await twitter.request_followers(count=3)
            print("Твои подписчики:")
            for follower in followers:
                print(follower)

        except twitter_errors.HTTPException as exc:
            print(f"Не удалось выполнить запрос. Статус аккаунта: {account.status.value}")
            raise exc
```
