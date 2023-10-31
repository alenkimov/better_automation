# Better Site Automation
[![Telegram channel](https://img.shields.io/endpoint?url=https://runkit.io/damiankrawczyk/telegram-badge/branches/master?url=https://t.me/cum_insider)](https://t.me/cum_insider)
[![PyPI version info](https://img.shields.io/pypi/v/better-automation.svg)](https://pypi.python.org/pypi/better-automation)
[![PyPI supported Python versions](https://img.shields.io/pypi/pyversions/better-automation.svg)](https://pypi.python.org/pypi/better-automation)


```bash
pip install better-automation
```


More libraries of the family:
- [better-web3](https://github.com/alenkimov/better_web3)
- [better-proxy](https://github.com/alenkimov/better_proxy)


## Прокси и User-Agent

Прокси и User-Agent должны передавать через сессию.

```python
from better_automation import twitter
from better_automation.utils import proxy_session

twitter_account = twitter.Account("auth_token")
async with proxy_session(
        proxy="example.com:2023", user_agent="Your User Agent"
) as session:
    twitter_client = twitter.Client(twitter_account, session)
```

Если параметр user_agent не задан, то будет задан случайный user_agent.

## Пример работы с Твиттер аккаунтом

```python
from better_automation import twitter
from better_automation.utils import proxy_session
from better_automation.twitter import errors as twitter_errors


async def twitter_demo():
    twitter_account = twitter.Account("auth_token")

    # В proxy_session() можно передать прокси и user-agent (по умолчанию присваивается рандомный)
    async with proxy_session() as session:
        twitter_client = twitter.Client(twitter_account, session)

        try:
            # Запрашиваем имя пользователя
            username = await twitter_client.request_username()
            print(f"Имя пользователя: {username}")

            # Запрашиваю различную информацию о пользователе
            info = await twitter_client.request_user_info(username)
            print(f"Всего подписчиков: {info['legacy']['followers_count']}")
            print(f"Аккаунт создан: {info['legacy']['created_at']}")

            # Запрашиваем свой user_id (кешируется)
            user_id = await twitter_client.request_user_id(username)
            print(f"Твой ID: {user_id}")

            # Запрашиваем первых трех подписчиков
            followers = await twitter_client.request_followers(user_id, count=3)
            print("Три твоих подписчика:")
            for user_id, username in followers.items():
                print(f"\t@{username} ({user_id})")

            # Смена имени и год рождения (год рождения нужно менять обязательно)
            print(f"Имя и дата рождения установлены: {await twitter_client.update_profile(1, 1, 2002, name='Hitori Gotoh')}")

            # Выражение любви через твит
            tweet_id = await twitter_client.tweet("I love YOU !!!!!")
            print(f"Любовь выражена! Tweet id: {tweet_id}")

            # Лайк
            print(f"Tweet {tweet_id} is liked: {await twitter_client.like(tweet_id)}")

            # Репост (ретвит)
            print(f"Tweet {tweet_id} is retweeted. Tweet id: {await twitter_client.repost(tweet_id)}")

            # Коммент (реплай)
            print(f"Tweet {tweet_id} is replied. Reply id: {await twitter_client.reply(tweet_id, 'tem razão')}")

            bind_data = {
                'response_type': 'code',
                'client_id': 'ZXh0SU5iS1pwTE5xclJtaVNNSjk6MTpjaQ',
                'redirect_uri': 'https://www.memecoin.org/farming',
                'scope': 'users.read tweet.read offline.access',
                'state': 'state',
                'code_challenge': 'challenge',
                'code_challenge_method': 'plain'
            }

            # Привязка приложения
            bind_code = await twitter_client.bind_app(**bind_data)
            print(f"Bind code: {bind_code}")

            # Запрашиваем id Илона Маска
            user_handle = "@elonmusk"
            elonmusk = await twitter_client.request_user_id(user_handle)

            # Подписываемся на Илона Маска
            print(f"{user_handle} is followed: {await twitter_client.follow(elonmusk)}")

            # Отписываемся от Илона Маска
            print(f"{user_handle} is unfollowed: {await twitter_client.unfollow(elonmusk)}")

            tweet_url = 'https://twitter.com/CreamIce_Cone/status/1691735090529976489'
            # Цитата (Quote tweet)
            quote_tweet_id = await twitter_client.quote(tweet_url, 'oh..')
            print(f"Quoted! Tweet id: {quote_tweet_id}")

        except twitter_errors.HTTPException as exc:
            print(f"Не удалось выполнить запрос. Статус аккаунта: {twitter_account.status.value}")
            raise exc
```
