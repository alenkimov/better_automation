import asyncio
from better_automation.playwright_ import BasePlaywrightBrowser
from better_automation.google import GooglePlaywrightBrowserContext, GoogleAccount
from better_proxy import Proxy

# Отловите подобную ссылку: https://accounts.google.com/o/oauth2/v2/auth?client_id=...
# Соберите с нее параметры для OAuth2 авторизации, подобные этим:
OAUTH2_DATA = {
    'access_type': 'offline',
    'client_id': '968583257586-kljtp79kj8nc53gocd7lmo3sfgbd2i1f.apps.googleusercontent.com',
    'gsiwebsdk': '3',
    'include_granted_scopes': 'true',
    'enable_granular_consent': 'true',
    'prompt': 'consent',
    'redirect_uri': 'https://airdrop.gomble.io/login',
    'response_type': 'code',
    'scope': 'https://www.googleapis.com/auth/userinfo.email',
}


async def main():
    # Загрузит Google аккаунты из файла или импортируйте их другим удобным способом
    google_accounts = GoogleAccount.from_file("google_accounts.txt", separator=":")
    proxies = Proxy.from_file("proxies.txt")

    # Создайте базовый браузер
    async with BasePlaywrightBrowser(headless=False) as browser:
        # for google_account in google_accounts:
        for proxy, google_account in zip(proxies, google_accounts):
            # Создайте новый контекст
            # async with browser.new_context() as context:
            async with browser.new_context(proxy=proxy) as context:
                # Создайте экземпляр GooglePlaywrightBrowserContext для взаимодействия с Google через эмуляцию
                #   на основе этого контекста и аккаунта Google
                google = GooglePlaywrightBrowserContext(
                    context, google_account, smshub_api_key='...')
                # Передайте найденные параметры для OAuth2 авторизации в метод oauth2
                await google.login()
                # oauth_code, redirect_url = await google.oauth2(**OAUTH2_DATA)
                # print(f"[{google_account}] {oauth_code}")
                # Полученный oauth_code передайте сервису для завершения привязки

asyncio.run(main())
