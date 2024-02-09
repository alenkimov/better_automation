# Better Site Automation
[![Telegram channel](https://img.shields.io/endpoint?url=https://runkit.io/damiankrawczyk/telegram-badge/branches/master?url=https://t.me/cum_insider)](https://t.me/cum_insider)

Набор инструментов для автоматизации:
- Все из библиотеки [tweepy-self](https://github.com/alenkimov/tweepy-self): логин, анлок, totp, OAuth, OAuth2, твиты, лайки, сообщения и многое другое..
- Дополнения для [discord.py-self](https://github.com/dolfies/discord.py-self) в виде метода для соглашения с правилами сервера.
- Google login и OAuth2 на [Playwright](https://github.com/microsoft/playwright).
- googleapis для OAuth2. Использовалось в Well3 (yogapetz) для авторизации и может использоваться в других проектах.

Особенности:
- Поддержка прокси в любом из существующих форматов благодаря [better-proxy](https://github.com/alenkimov/better_proxy)
- Все (кроме Google) на запросах через [curl_cffi](https://github.com/yifeikong/curl_cffi)

More libraries of the family:
- [tweepy-self](https://github.com/alenkimov/tweepy-self)
- [better-web3](https://github.com/alenkimov/better_web3)
- [better-proxy](https://github.com/alenkimov/better_proxy)

## Installation
pip
```bash
pip install git+https://github.com/alenkimov/better_automation.git@pre-release#egg=better_automation
```

poetry
```bash
poetry add better-automation --git https://github.com/alenkimov/better_automation.git --rev pre-release
```
