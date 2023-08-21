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
        
        # Подписываемся на Илона Маска
        user_handle = "@elonmusk"
        user_id = await twitter.request_user_id(user_handle)
        print(f"{user_handle} is followed: {await twitter.follow(user_id)}")
        
        # Загружаем твит с аниме девочкой
        img_url = "https://cdn.donmai.us/original/26/cd/__chloe_von_einzbern_fate_and_1_more_drawn_by_anzu_ame__26cdf525d657a8c14cc8758160bc6284.jpg"
        media_id = await twitter.upload_image(img_url)
        print(f"Media id: {media_id}")
        tweet_id = await twitter.tweet("I love YOU!!!!", media_id=media_id)
        print(f"Tweet {tweet_id} is pinned: {await twitter.pin_tweet(tweet_id)}")
        
        # Запрашиваем информацию о твите
        tweet_data = await twitter.request_tweet_data(tweet_id)
        print(tweet_data)
        
        # Ретвит, лайк, реплай
        another_tweet_id = 1692431667548528661
        print(f"Tweet {another_tweet_id} is retweeted. Tweet id: {await twitter.retweet(another_tweet_id)}")
        print(f"Tweet {another_tweet_id} is liked: {await twitter.like(another_tweet_id)}")
        print(f"Tweet {another_tweet_id} is replied. Reply id: {await twitter.reply(another_tweet_id, 'I love YOU!!!')}")
```
