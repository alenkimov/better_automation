# Better Site Automation
[![Telegram channel](https://img.shields.io/endpoint?url=https://runkit.io/damiankrawczyk/telegram-badge/branches/master?url=https://t.me/cum_insider)](https://t.me/cum_insider)

Набор инструментов для автоматизации:
- Поддержка прокси в любом из существующих форматов
- Все (кроме Google) на запросах через curl_cffi
- Все аккаунты — Pydantic модели
- Google login
- Google OAuth2
- Google привязка номера с smshub
- Все из библиотеки [discord.py-self](https://github.com/dolfies/discord.py-self) + Discord joiner с соглашением с правилами сервера (без решения капчи)
- Все из библиотеки [tweepy-self](https://github.com/alenkimov/tweepy-self): логин, анлок, totp, OAuth, OAuth2, твиты, лайки, сообщения и многое другое..
- googleapis для OAuth2. Использовалось в Well3 (yogapetz) для авторизации и может использоваться в других проектах.

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
