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
Взаимодействие происходит через слегка модифицированную асинхронную сессию из библиотеки [curl_cffi](https://github.com/yifeikong/curl_cffi).

В дальнейшем работать напрямую с сессией не придется. 
Клиенты для Twitter и Discord сами создадут сессию внутри себя.
Вы можете использовать эту сессию для создания собственных оберток над API.

Вот так можно создать сессию с прокси:
```python
from better_automation.base import BaseAsyncSession

async def main():
  async with BaseAsyncSession(proxy="http://login:password@host:port") as session:
    ...
```

Если вы работаете под Windows, то может потребоваться дополнительная настройка перед совершением запросов ([подробнее](https://curl-cffi.readthedocs.io/en/latest/faq/#not-working-on-windows-notimplementederror)):
```python
from better_automation.utils import set_windows_selector_event_loop_policy

set_windows_selector_event_loop_policy()
```

Если вы имеете проблемы с SSL сертификатами, то задайте параметр `verify=False` для сессии:
```python
async with BaseAsyncSession(verify=False) as session:
    ...
```

Пример работы сессией:
```python
import asyncio
from pprint import pprint

from better_automation.base import BaseAsyncSession
from better_automation.utils import set_windows_selector_event_loop_policy

set_windows_selector_event_loop_policy()

PROXY = None  # "http://login:password@host:port"


async def curl_cffi_example(proxy: str = None):
    async with BaseAsyncSession(proxy=proxy, verify=False) as session:
        response = await session.get("https://ipapi.co/json")
        response_json = response.json()
        print(f"{response_json["ip"]} {response_json["country_name"]}")
        
        response = await session.get("https://tls.browserleaks.com/json")
        response_json = response.json()
        pprint(response_json)


if __name__ == '__main__':
    asyncio.run(curl_cffi_example(PROXY))
```

## BaseAccount: работа с файлами
Классы `TwitterAccount` и `DiscordAccount` наследуются от `BaseAccount`,
а значит имеют методы `from_file()` и `to_file()` для работы с файлами.

Допустим у нас есть файл `discords.txt` с Discord аккаунтами следующего формата: `auth_token;email;password`

Вот так выглядит загрузка аккаунтов из такого файла:
```python
from better_automation.discord import DiscordAccount

accounts = DiscordAccount.from_file("discords.txt", separator=";", fields=("auth_token", "email", "password"))
```

Допустим мы хотим изменить формат на следующий: `auth_token:password:email`

Вот так выглядит сохранение аккаунтов в файл:
```python
from better_automation.discord import DiscordAccount

accounts: list[DiscordAccount]
DiscordAccount.to_file("discords.txt", accounts, separator=":", fields=("auth_token", "password", "email"))
```

## Интеграция better-proxy
Чтобы работа с прокси была более приятная, рекомендую использовать библиотеку [better-proxy](https://github.com/alenkimov/better_proxy).
Это позволит принимать прокси в любом формате и загружать их из файла одной строчкой кода.

Для удобства можно создать контекстный менеджер, который по умолчанию отключает проверку SSL сертификатов и принимает прокси в формате better-proxy:
```python
from contextlib import asynccontextmanager
from typing import AsyncContextManager

from better_automation.discord import DiscordAccount, DiscordClient
from better_automation.twitter import TwitterAccount, TwitterClient
from better_proxy import Proxy


@asynccontextmanager
async def discord_client(
        account: DiscordAccount,
        proxy: Proxy = None,
        verify: bool = False,
        **kwargs,
) -> AsyncContextManager[DiscordClient]:
    async with DiscordClient(account, proxy=proxy.as_url if proxy else None, verify=verify, **kwargs) as discord:
        yield discord


@asynccontextmanager
async def twitter_client(
        account: TwitterAccount,
        proxy: Proxy = None,
        verify: bool = False,
        **kwargs,
) -> AsyncContextManager[TwitterClient]:
    async with TwitterClient(account, proxy=proxy.as_url if proxy else None, verify=verify, **kwargs) as twitter:
        yield twitter
```

## Twitter
Библиотека позволяет работать с неофициальным API Twitter, а именно:
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
- И другое.

### TwitterAccount
Аккаунт можно создать из auth_token'а, а также cookies в формате JSON или base64:
```python
from better_automation.twitter import TwitterAccount

account = TwitterAccount("auth_token", password="password")
account = TwitterAccount.from_cookies("JSON cookies")
account = TwitterAccount.from_cookies("base64 cookies", base64=True)
```

#### Статус аккаунта
После любого взаимодействия с Twitter устанавливается статус аккаунта:
- `BAD_TOKEN` - Неверный токен.
- `UNKNOWN` - Статус аккаунта не установлен.
- `SUSPENDED` - Действие учетной записи приостановлено (бан).
- `LOCKED` - Учетная запись заморожена (лок) (требуется прохождение капчи).
- `GOOD` - Аккаунт в порядке.

Не каждое взаимодействие с Twitter достоверно определяет статус аккаунта.
Например, простой запрос данных об аккаунте честно вернет данные, даже если ваш аккаунт заморожен.

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
Демонстрационные скрипты:
- [Установка статуса аккаунтов (проверка на блокировку, заморозку)](https://github.com/alenkimov/better_automation/blob/main/examples/twitter/account_checker.py)
- [Голосование](https://github.com/alenkimov/better_automation/blob/main/examples/twitter/voter.py)

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

bind_code = await twitter.oauth_2(**bind_data)
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
Библиотека позволяет работать с неофициальным API Discord, а именно:
- Привязывать сервисы (приложения).
- Устанавливать статус токена (недействительный токен).
- Ловить флаги аккаунта (спаммер, карантин).
- Заходить на сервер и всячески взаимодействовать с ним.
- Запрашивать различную информацию.
- И другое.

Многие методы были перенесены из библиотеки [discum](https://github.com/Merubokkusu/Discord-S.C.U.M) и не тестировались.

### DiscordAccount
Аккаунт можно создать из токена авторизации:
```python
from better_automation.discord import DiscordAccount

account = DiscordAccount("auth_token")
```

#### Статус аккаунта и флаги
После любого взаимодействия с Discord устанавливается статус аккаунта:
- `UNKNOWN` - Статус аккаунта не установлен.
- `BAD_TOKEN` - Неверный токен или бан.
- `GOOD` - Аккаунт в порядке.

Также аккаунт проверяется на флаги (спамер, на карантине).
За состояние флагов отвечают переменные `DiscordAccount.is_spammer` и `DiscordAccount.is_quarantined`.

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
Демонстрационные скрипты:
- [Discord Joiner](https://github.com/alenkimov/better_automation/blob/main/examples/discord/guild_joiner.py)
- [Discord Token Checker](https://github.com/alenkimov/better_automation/blob/main/examples/discord/account_checker.py)

Привязка сервиса (приложения):

```python
# Изучите запросы сервиса и найдите подобные данные для авторизации (привязки):
bind_data = {
    'client_id': '986938000388796468',
    'response_type': 'code',
    'scope': 'identify guilds guilds.members.read',
}

# Привязка приложения
bind_code = await discord.oauth_2(**bind_data)
print(f"Bind code: {bind_code}")

# Передайте код авторизации (привязки) сервису.
# Сервис также может потребовать state, если он динамический.
```

## Не реализовано
- [ ] (Twitter) [Unlocker](https://github.com/0xStarLabs/StarLabs-Twitter/blob/master/self/utilities/solve_twitter_captcha.py)
- [ ] (Twitter) Oauth старого типа

## Credits
- [0xStarLabs](https://github.com/0xStarLabs) / [StarLabs-Discord](https://github.com/0xStarLabs/StarLabs-Discord)
- [0xStarLabs](https://github.com/0xStarLabs) / [StarLabs-Twitter](https://github.com/0xStarLabs/StarLabs-Twitter)
- [Merubokkusu](https://github.com/Merubokkusu) / [Discord-S.C.U.M](https://github.com/Merubokkusu/Discord-S.C.U.M)
- [makarworld](https://github.com/makarworld) / [TwitterBot](https://github.com/makarworld/TwitterBot)
- [Rapptz](https://github.com/Rapptz) / [discord.py](https://github.com/Rapptz/discord.py)
- [tweepy](https://github.com/tweepy) / [tweepy](https://github.com/tweepy/tweepy)