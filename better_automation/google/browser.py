import re
from typing import Literal

from yarl import URL
from playwright.async_api import BrowserContext, Request, TimeoutError
from playwright_stealth import stealth_async
from .errors import CaptchaRequired
from .account import GoogleAccount


PromptType = Literal["consent", "select_account"] | None


class GooglePlaywrightBrowserContext:
    MY_ACCOUNT_URL_PATTERN = re.compile(r"https://myaccount\.google\.com.*")

    def __init__(
            self,
            context: BrowserContext,
            account: GoogleAccount,
            *,
            stealth: bool = False,
    ):
        self._context = context
        self.account = account
        self.stealth = stealth

        self._logged_in: bool = False
        self._needs_recovery_email: bool = False

    async def new_page(self):
        page = await self._context.new_page()
        if self.stealth: await stealth_async(page)
        return page

    async def login(self):
        page = await self.new_page()
        await page.goto("https://accounts.google.com/ServiceLogin")
        await page.locator('xpath=//*[@id="identifierId"]').fill(self.account.email)
        await page.locator('xpath=//*[@id="identifierNext"]/div/button/div[3]').click()
        await page.wait_for_load_state("networkidle")
        if await page.locator('xpath=//iframe[@title="reCAPTCHA"]').count() > 0:
            raise CaptchaRequired("Обнаружена reCAPTCHA.")
        await page.locator('xpath=//*[@id="password"]/div[1]/div/div[1]/input').fill(self.account.password)
        await page.locator('xpath=//*[@id="passwordNext"]/div/button/span').click()

        # На новых аккаунтах может выскакивать назойливое напоминание
        try:
            await page.get_by_text("Not now").click(timeout=5_000)
        except TimeoutError:
            pass

        # Если в аккаунт с этого IP не входили ранее, то попросит ввести recovery_email
        recovery_email_button = page.locator('div[data-challengeid="5"]')
        try:
            await recovery_email_button.wait_for()
            self._needs_recovery_email = True
        except TimeoutError:
            self._needs_recovery_email = False
            pass

        if self._needs_recovery_email:
            if not self.account.recovery_email:
                raise ValueError(f"Needs recovery email")

            await recovery_email_button.click()
            await page.locator('xpath=//input[@id="knowledge-preregistered-email-response"]').fill(self.account.recovery_email)
            await page.get_by_text("Next").click()
            await page.get_by_text("Not now").click()
            self._needs_recovery_email = False

        await page.wait_for_url(self.MY_ACCOUNT_URL_PATTERN)
        self._logged_in = True
        await page.close()

    async def oauth2(
            self,
            *,
            client_id: str,
            redirect_uri: str,
            scope: str,
            gsiwebsdk: int = 3,
            access_type: str = "offline",
            response_type: str = "code",
            prompt: PromptType = None,
            include_granted_scopes: bool | str = True,
            enable_granular_consent: bool | str = True,
    ) -> tuple[str | None, str | None]:
        """
        Найдите подобную ссылку: https://accounts.google.com/o/oauth2/v2/auth?client_id=...
        Передайте параметры ссылки (после знака вопроса (?)) в метод oauth2
        Метод вернет oauth_code и redirect_url (также содержится в redirect_url)
        :return: oauth_code, redirect_url
        """
        if not self._logged_in:
            await self.login()

        oauth_url = "https://accounts.google.com/o/oauth2/v2/auth"
        params = {
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "gsiwebsdk": gsiwebsdk,
            "access_type": access_type,
            "response_type": response_type,
            "include_granted_scopes": str(include_granted_scopes).lower(),
            "enable_granular_consent": str(enable_granular_consent).lower(),
        }
        if prompt: params["prompt"] = prompt
        oauth_url = str(URL(oauth_url).with_query(params))
        page = await self.new_page()

        oauth_code = None
        redirect_url = None

        async def request_handler(request: Request):
            print()
            nonlocal oauth_code
            nonlocal redirect_url

            # Поимка oauth_code и redirect_url основана на знании того, что гугл делает такой редирект:
            # https://developers.google.com/identity/protocols/oauth2/javascript-implicit-flow#redirecting
            if request.url.startswith(redirect_uri):
                redirect_url = URL(request.url)
                oauth_code = redirect_url.query.get(response_type)

        page.on("request", request_handler)

        await page.goto(oauth_url)
        # TODO Поведение страницы может отличаться, если значение prompt != "consent"
        await page.locator(f'[data-identifier="{self.account.email}"]').click()
        await page.wait_for_load_state("networkidle")
        try:
            await page.get_by_text("Continue", exact=True).click(no_wait_after=True, timeout=5_000)
        except TimeoutError:
            pass
        await page.wait_for_load_state("networkidle")
        await page.close()
        return oauth_code, str(redirect_url)
