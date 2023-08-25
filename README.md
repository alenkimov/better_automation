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

```python
import aiohttp
from better_automation import TwitterAPI

async def twitter_demo():
    async with aiohttp.ClientSession() as session:
        twitter = TwitterAPI(session, "auth_token")
        # Запрашиваем имя пользователя
        username = await twitter.request_username()
        print(f"Your username: {username}")

        # Запрашиваем свой user_id
        user_id = await twitter.request_user_id(username)
        print(f"Your user id: {user_id}")

        # Запрашиваем первых трех подписчиков
        followers = await twitter.request_followers(user_id, count=3)
        print("Your followers:")
        for user_id, username in followers.items():
            print(f"\t@{username} ({user_id})")

        # Загружаем изображение с Хитори на сервер
        img_url = "https://cdn.donmai.us/sample/d8/c1/__gotoh_hitori_bocchi_the_rock_drawn_by_pigbone_cafe__sample-d8c1495c647769dfe34c697a17e91196.jpg"
        media_id = await twitter.upload_image(img_url)
        print(f"Media id: {media_id}")

        # Ставим банер
        print(f"Banner is changed: {await twitter.update_profile_banner(media_id)}!")

        # Ставим аватарку
        print(f"Avatar is changed: {await twitter.update_profile_avatar(media_id)}!")

        # Меняем имя и год рождения (год рождения нужно менять обязательно)
        print(f"Name is changed: {await twitter.update_profile(1, 1, 2002, name='Hitori Gotoh')}")

        # Выражаем нашу любовь к Хитори через твит с ее изображением
        tweet_id = await twitter.tweet("I love YOU!!!!", media_id=media_id)
        print(f"Tweeted: {tweet_id}")

        # Закрепляем твит
        print(f"Tweet {tweet_id} is pinned: {await twitter.pin_tweet(tweet_id)}")

        # Запрашиваем информацию о твите (пока что возвращает все данные, поэтому метод приватный)
        # tweet_data = await twitter._request_tweet_data(tweet_id)
        # pprint(tweet_data)

        another_tweet_id = 1694061696187335072

        # Лайк
        print(f"Tweet {another_tweet_id} is liked: {await twitter.like(another_tweet_id)}")

        # Репост (ретвит)
        print(f"Tweet {another_tweet_id} is retweeted. Tweet id: {await twitter.repost(another_tweet_id)}")

        # Коммент (реплай)
        print(f"Tweet {another_tweet_id} is replied. Reply id: {await twitter.reply(another_tweet_id, 'tem razão')}")
        
        bind_data = {
            'response_type': 'code',
            'client_id': 'aTk5eEUxZlpvak1RYU9yTEZhZ0M6MTpjaQ',
            'scope': 'tweet.read users.read follows.read like.read offline.access',
            'code_challenge': 'challenge',
            'code_challenge_method': 'plain',
            'redirect_uri': 'https://taskon.xyz/twitter',
            'state': '0058371f-41cf-11ee-9397-7e1ed119aa82',
        }
        
        # Привязка приложения
        bind_code = await twitter.bind_app(**bind_data)
        print(f"Bind code: {bind_code}")

        # Запрашиваем id Илона Маска
        user_handle = "@elonmusk"
        elonmusk = await twitter.request_user_id(user_handle)

        # Подписываемся на Илона Маска
        print(f"{user_handle} is followed: {await twitter.follow(elonmusk)}")

        # Отписываемся от Илона Маска
        print(f"{user_handle} is unfollowed: {await twitter.unfollow(elonmusk)}")

        tweet_url = 'https://twitter.com/CreamIce_Cone/status/1691735090529976489'
        # Цитата (Quote tweet)
        quote_tweet_id = await twitter.quote(tweet_url, 'oh..')
        print(f"Quoted! Tweet id: {quote_tweet_id}")
```
