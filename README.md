# Better Site Automation
[![Telegram channel](https://img.shields.io/endpoint?url=https://runkit.io/damiankrawczyk/telegram-badge/branches/master?url=https://t.me/cum_insider)](https://t.me/cum_insider)
[![PyPI version info](https://img.shields.io/pypi/v/better-automation.svg)](https://pypi.python.org/pypi/better-automation)
[![PyPI supported Python versions](https://img.shields.io/pypi/pyversions/better-automation.svg)](https://pypi.python.org/pypi/better-automation)

```bash
pip install better-automation
```

- Unofficial Twitter and Discord API

More libraries of the family:
- [better-web3](https://github.com/alenkimov/better_web3)
- [better-proxy](https://github.com/alenkimov/better_proxy)

## BaseSession
Взаимодействие с Twitter происходит через слегка модифицированную асинхронную сессию из библиотеки [curl_cffi](https://github.com/yifeikong/curl_cffi).

Вот так можно создать сессию с прокси:
```python
from better_automation.base import BaseAsyncSession

async def main():
  async with BaseAsyncSession(proxy="http://login:password@host:port") as session:
    ...
```

Если вы работаете под Windows, то может потребоваться дополнительная настройка перед совершением запросов ([подробнее](https://curl-cffi.readthedocs.io/en/latest/faq/#not-working-on-windows-notimplementederror)):
```python
import sys, asyncio

def set_windows_event_loop_policy():
    if sys.version_info >= (3, 8) and sys.platform.lower().startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

set_windows_event_loop_policy()
```

Если вы имеете проблемы с SSL сертификатами, то задайте параметр `verify=False` для сессии:
```python
async with BaseAsyncSession(verify=False) as session:
    ...
```

Пример работы сессией:
```python
import sys
import asyncio
from pprint import pprint

from better_automation.base import BaseAsyncSession


PROXY = None  # "http://login:password@host:port"


def set_windows_event_loop_policy():
    if sys.version_info >= (3, 8) and sys.platform.lower().startswith("win"):
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


async def curl_cffi_example(proxy: str = None):
    async with BaseAsyncSession(proxy=proxy, verify=False) as session:
        response = await session.get("https://ipapi.co/json")
        response_json = response.json()
        print(f"{response_json['ip']} {response_json['country_name']}")
        
        response = await session.get("https://tls.browserleaks.com/json")
        response_json = response.json()
        pprint(response_json)


if __name__ == '__main__':
    set_windows_event_loop_policy()
    asyncio.run(curl_cffi_example(PROXY))
```

В дальнейшем работать напрямую с сессией не придется. 
Клиенты для Twitter и Discord сами создадут сессию внутри себя.

## Twitter
Библиотека позволяет работать с неофициальным API Twitter.

А именно:
- Привязывать сервисы (приложения).
- Устанавливать статус аккаунта (бан, лок).
- Загружать изображения на сервер и изменять баннер и аватарку.
- Изменять данные о пользователе: имя, описание профиля и другое.
- Изменять имя пользователя и пароль.
- Запрашивать информацию о подписчиках.
- Запрашивать некоторую информацию о пользователе (количество подписчиков и другое).
- Голосовать.
- Подписываться и отписываться.
- Лайкать и дизлайкать.
- Твиттить, ретвиттить с изображением и без.
- Закреплять твиты.
- Удалять твиты.
- ...

### TwitterAccount
Аккаунт представляет собой контейнер для следующих данных:
- Токены авторизации: `auth_token` и `x-csrf-token (ct0)`.
- Имя пользователя (username) и пароль.
- ID пользователя.

Аккаунт можно создать из auth_token'а, cookies в формате JSON или base64:
```python
from better_automation.twitter import TwitterAccount

# Аккаунту можно задать пароль (требуется для смены пароля)
account = TwitterAccount("auth_token", password="password")
account = TwitterAccount.from_cookies("JSON cookies")
account = TwitterAccount.from_cookies("base64 cookies", base64=True)
```

Аккаунты можно загрузить напрямую из файла:
```python
accounts = TwitterAccount.from_file("twitter_auth_tokens.txt")
accounts = TwitterAccount.from_file("twitter_json_cookies.txt", cookies=True)
accounts = TwitterAccount.from_file("twitter_base64_cookies.txt", cookies=True, base64=True)
```

После любого взаимодействия с Twitter устанавливается статус аккаунта:
- `BAD_TOKEN` - Неверный токен.
- `UNKNOWN` - Статус аккаунта не установлен.
- `SUSPENDED` - Действие учетной записи приостановлено (бан).
- `LOCKED` - Учетная запись заморожена (лок) (требуется прохождение капчи).
- `GOOD` - Аккаунт в порядке.

### TwitterClient
Для взаимодействия с Twitter нужно создать экземпляр класса TwitterClient, передав в него аккаунт.

В клиента можно передавать параметры сессии, включая:
- Прокси в формате `http://login:password@host:port`.
- `verify=False` для отключения проверки SSL сертификатов.

```python
from better_automation.twitter import TwitterAccount, TwitterClient

account = TwitterAccount("auth_token", password="password")
proxy = "http://login:password@host:port"

async with TwitterClient(account, proxy=proxy, verify=False) as twitter:
    ...
```

### Примеры работы
Список доступных методов:
- `bind_app(**bind_data) -> bind_code` Привязка (авторизация) стороннего сервиса
- `upload_image(image) -> media_id`
- `tweet(text, media_id)`
- `repost(tweet_id)`
- `quote(tweet_url, text, media_id)`
- `reply(tweet_id, text, media_id)`
- `like(tweet_id)`
- `unlike(tweet_id)`
- `follow(user_id)`
- `unfollow(user_id)`
- `pin_tweet(tweet_id)`
- `delete_tweet(tweet_id)`
- `change_password(password)`
- `change_username(username)`
- `update_profile(name, description, location)`
- `update_profile_banner(media_id)`
- `update_profile_avatar(media_id)`
- `request_user_data(username) -> UserData`
- `request_followings(user_id) -> list[UserData]`
- `request_followers(user_id) -> list[UserData]`

Демонстрационные скрипты (папка `examples/twitter`)`:
- Установка статуса аккаунтов (проверка на блокировку, заморозку)
- Голосование

Запрос информации о пользователе:
```python
# Запрос информации о текущем пользователе:
me = await twitter.request_user_data()
print(f"[{account.short_auth_token}] {me}")
print(f"Аккаунт создан: {me.created_at}")
print(f"Following (подписан ты): {me.followings_count}")
print(f"Followers (подписаны на тебя): {me.followers_count}")
print(f"Прочая информация: {me.raw_data}")

# Запрос информации об ином пользователе:
elonmusk = await twitter.request_user_data("@elonmusk")
print(elonmusk)
```

Смена имени пользователя и пароля:
```python
account = TwitterAccount("auth_token", password="password")
...
await twitter.change_username("new_username")
await twitter.request_user_data()
print(f"New username: {account.data.username}")

await twitter.change_password("new_password")
print(f"New password: {account.password}")
print(f"New auth_token: {account.auth_token}")
```

Смена данных профиля:
```python
await twitter.update_birthdate(day=1, month=12, year=2000)
await twitter.update_profile(  # Locks account!
    name="New Name",
    description="New description",
    location="New York",
    website="https://github.com/alenkimov/better_automation",
)
```

Загрузка изображений и смена аватара и баннера:
```python
image = open(f"image.png", "rb").read()
media_id = await twitter.upload_image(image)
avatar_image_url = await twitter.update_profile_avatar(media_id)
banner_image_url = await twitter.update_profile_banner(media_id)
```

Привязка сервиса (приложения):
```python
# Изучите запросы сервиса и найдите подобные данные для авторизации (привязки):
bind_data = {
    'response_type': 'code',
    'client_id': 'TjFVQm52ZDFGWEtNT0tKaktaSWU6MTpjaQ',
    'redirect_uri': 'https://waitlist.lens.xyz/tw/',
    'scope': 'users.read tweet.read offline.access',
    'state': 'state',  # Может быть как статичным, так и динамическим.
    'code_challenge': 'challenge',
    'code_challenge_method': 'plain'
}

bind_code = await twitter.bind_app(**bind_data)
# Передайте код авторизации (привязки) сервису.
# Сервис также может потребовать state, если он динамический.
```

Отправка сообщения:
```python
bro = await twitter.request_user_data("@username")
await twitter.send_message(bro.id, "I love you!")
```

Запрос входящих сообщений:
```python
messages = await twitter.request_messages()
for message in messages:
    message_data = message["message_data"]
    recipient_id = message_data["recipient_id"]
    sender_id = message_data["sender_id"]
    text = message_data["text"]
    print(f"[id  {sender_id}] -> [id {recipient_id}]: {text}")
```

Другие методы:
```python
# Выражение любви через твит
tweet_id = await twitter.tweet("I love YOU! !!!!1!1")
print(f"Любовь выражена! Tweet id: {tweet_id}")

print(f"Tweet is pined: {await twitter.pin_tweet(tweet_id)}")

# Лайк
print(f"Tweet {tweet_id} is liked: {await twitter.like(tweet_id)}")

# Репост (ретвит)
print(f"Tweet {tweet_id} is retweeted. Tweet id: {await twitter.repost(tweet_id)}")

# Коммент (реплай)
print(f"Tweet {tweet_id} is replied. Reply id: {await twitter.reply(tweet_id, 'tem razão')}")

# Подписываемся на Илона Маска
print(f"@{elonmusk.username} is followed: {await twitter.follow(elonmusk.id)}")

# Отписываемся от Илона Маска
print(f"@{elonmusk.username} is unfollowed: {await twitter.unfollow(elonmusk.id)}")

tweet_url = 'https://twitter.com/CreamIce_Cone/status/1691735090529976489'
# Цитата (Quote tweet)
quote_tweet_id = await twitter.quote(tweet_url, 'oh....')
print(f"Quoted! Tweet id: {quote_tweet_id}")

# Запрашиваем первых трех подписчиков
# (Параметр count по каким-то причинам работает некорректно)
followers = await twitter.request_followers(count=20)
print("Твои подписчики:")
for follower in followers:
    print(follower)
```

## Discord
Библиотека позволяет работать с неофициальным API Discord.

А именно:
- Привязывать сервисы (приложения).
- Ловить флаги аккаунта (спаммер, карантин).
- Отправлять сообщения на сервер. Ставить реакции.
- Нажимать кнопки на сервере. (не тестировалось!)

### DiscordAccount
Аккаунт представляет собой контейнер для следующих данных:
- Токен авторизации.
- Имя пользователя (username) и пароль.

Аккаунт можно создать из токена авторизации:
```python
from better_automation.discord import DiscordAccount

account = DiscordAccount("auth_token")
```

Аккаунты можно загрузить напрямую из файла:
```python
accounts = DiscordAccount.from_file("discord_tokens.txt")
```

После любого взаимодействия с Discord устанавливается статус аккаунта:
- `BAD_TOKEN` - Неверный токен.
- `UNKNOWN` - Статус аккаунта не установлен.
- `BANNED` - Бан.
- `GOOD` - Аккаунт в порядке.

Баны сейчас не отлавливаются. Зато отлавливается статус `BAD_TOKEN`.

### DiscordClient
Для взаимодействия с Discord нужно создать экземпляр класса DiscordClient, передав в него аккаунт.

В клиента можно передавать параметры сессии, включая:
- Прокси в формате `http://login:password@host:port`.
- `verify=False` для отключения проверки SSL сертификатов.

```python
from better_automation.discord import DiscordAccount, DiscordClient

account = DiscordAccount("auth_token", password="password")
proxy = "http://login:password@host:port"

async with DiscordClient(account, proxy=proxy, verify=False) as discord:
    ...
```

### Примеры работы
Список доступных методов:
- `bind_app(**bind_data) -> bind_code` Привязка (авторизация) стороннего сервиса
- `request_messages` и `request_message`
- `press_button`
- `send_reaction`
- `send_guild_chat_message`

Привязка сервиса (приложения):
```python
# Изучите запросы сервиса и найдите подобные данные для авторизации (привязки):
BIND_DATA = {
    'client_id': '986938000388796468',
    'response_type': 'code',
    'scope': 'identify guilds guilds.members.read',
}

# Привязка приложения
bind_code = await discord.bind_app(**bind_data)
print(f"Bind code: {bind_code}")

# Передайте код авторизации (привязки) сервису.
# Сервис также может потребовать state, если он динамический.
```

## Не реализовано
- [ ] (Twitter) [Unlocker](https://github.com/0xStarLabs/StarLabs-Twitter/blob/master/self/utilities/solve_twitter_captcha.py)
- [ ] (Twitter) Oauth старого типа
- [ ] (Discord) Всё из [Discord-S.C.U.M](https://github.com/Merubokkusu/Discord-S.C.U.M)

## Credits
- [0xStarLabs](https://github.com/0xStarLabs) / [StarLabs-Discord](https://github.com/0xStarLabs/StarLabs-Discord)
- [0xStarLabs](https://github.com/0xStarLabs) / [StarLabs-Twitter](https://github.com/0xStarLabs/StarLabs-Twitter)
- [Merubokkusu](https://github.com/Merubokkusu) / [Discord-S.C.U.M](https://github.com/Merubokkusu/Discord-S.C.U.M)
- [makarworld](https://github.com/makarworld) / [TwitterBot](https://github.com/makarworld/TwitterBot)
- [Rapptz](https://github.com/Rapptz) / [discord.py](https://github.com/Rapptz/discord.py)
- [tweepy](https://github.com/tweepy) / [tweepy](https://github.com/tweepy/tweepy)