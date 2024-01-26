import re
from typing import Literal

from yarl import URL
from playwright.async_api import BrowserContext, Request, TimeoutError
from playwright_stealth import stealth_async
from .errors import CaptchaRequired, FailedToOAuth2, FailedToLogin, RecoveryRequired, RecoveryEmailRequired
from .account import GoogleAccount, GoogleAccountStatus
from .utils import check_cookies


PromptType = Literal["consent", "select_account"] | None


def are_valid_google_cookies(cookies: list[dict]) -> bool:
    """
    SID и HSID: Эти cookie содержат цифровые подписи и информацию о последнем входе в систему.
    SSID, APISID, SAPISID: Также содержат информацию об аутентификации и используются в различных сервисах Google для поддержания сессии пользователя.
    __Secure*: Хотя они в первую очередь используются для рекламных целей, они также связаны с твоей учетной записью и могут содержать важную информацию о сессии.
    NID: Используется для хранения настроек пользователя и может содержать информацию, упрощающую доступ к аккаунту.
    GAPS: Этот cookie используется для аутентификации в различных приложениях Google и может содержать важные данные аутентификации.

    Все cookie, содержащие информацию об аутентификации:
        SID
        HSID
        SSID
        APISID
        SAPISID
        OTZ
        NID
        OSID
        LSID
        SIDCC
        ACCOUNT_CHOOSER
        __Secure-1PSIDTS
        __Secure-3PSIDTS
        __Secure-1PSID
        __Secure-3PSID
        __Secure-1PAPISID
        __Secure-3PAPISID
        __Secure-1PSIDCC
        __Secure-3PSIDCC
        __Secure-OSID
        __Host-1PLSID
        __Host-3PLSID
        __Host-GAPS
    """
    return check_cookies(cookies, {"SID", "HSID"})


class GooglePlaywrightBrowserContext:
    # Logining
    # # XPATH::COMMON
    _LEFT_BUTTON_XPATH = '//div[@jsname="QkNstf"]/div/div/button'  # Not now, Try another way
    _RIGHT_BUTTON_XPATH = '//div[@jsname="Njthtb"]/div/button'  # Continue, Send, Next

    # # XPATH
    _EMAIL_FIELD_XPATH = '//*[@id="identifierId"]'
    _EMAIL_CONFIRMATION_BUTTON_XPATH = '//*[@id="identifierNext"]/div/button'
    _RECAPTCHA_IFRAME_XPATH = '//iframe[@title="reCAPTCHA"]'
    _PASSWORD_FIELD_XPATH = '//*[@id="password"]/div[1]/div/div[1]/input'
    _PASSWORD_CONFIRMATION_BUTTON_XPATH = '//*[@id="passwordNext"]/div/button'
    _RECOVERY_EMAIL_BUTTON_XPATH = '//div[@data-challengeid="5"]'
    _RECOVERY_EMAIL_FIELD_XPATH = '//input[@id="knowledge-preregistered-email-response"]'
    _RECOVERY_BUTTON_XPATH = '//div[@id="accountRecoveryButton"]/div/div/a'

    # # PATTERNS
    _RECOVERY_REQUIRED_URL_PATTERN = re.compile(r"https://accounts\.google\.com/v3/signin/rejected.*")
    _PASSKEY_URL_PATTERN = re.compile(r"https://accounts\.google\.com/signin/v2/passkeyenrollment.*")
    _MY_ACCOUNT_URL_PATTERN = re.compile(r"https://myaccount\.google\.com.*")
    _GDS_URL_PATTERN = re.compile(r"https://gds\.google\.com.*")
    _LOGGED_IN_URL_PATTERNS = (_MY_ACCOUNT_URL_PATTERN, _GDS_URL_PATTERN)

    # OAuth2
    # # XPATH
    _CONTINUE_BUTTON_XPATH = '//div[@jsname="uRHG6"]/div/button'
    _ACCOUNT_BUTTON_XPATH = '//*[@data-identifier="{email}"]'

    def __init__(
            self,
            context: BrowserContext,
            account: GoogleAccount,
            *,
            stealth: bool = False,
            timeout_to_wait: int = 10_000,
    ):
        self._context = context
        self.account = account
        self.stealth = stealth
        self.timeout_to_wait = timeout_to_wait

        self._logged_in: bool = False
        self._needs_recovery_email: bool = False

    def _account_button_xpath(self) -> str:
        return self._ACCOUNT_BUTTON_XPATH.format(email=self.account.email.lower())

    async def _new_page(self):
        page = await self._context.new_page()
        if self.stealth: await stealth_async(page)
        return page

    def logged_in(self) -> bool:
        return self._logged_in

    async def login(self):
        if self.account.cookies:
            if not are_valid_google_cookies(self.account.cookies):
                self.account.status = GoogleAccountStatus.BAD_COOKIES
                return

            await self._context.add_cookies(self.account.cookies)
            self.account.status = GoogleAccountStatus.GOOD
            self._logged_in = True
            return

        page = await self._new_page()
        try:
            await page.goto("https://accounts.google.com/ServiceLogin")
            await page.locator(self._EMAIL_FIELD_XPATH).type(self.account.email)
            await page.locator(self._EMAIL_CONFIRMATION_BUTTON_XPATH).click()
            await page.wait_for_load_state("networkidle")
            if await page.locator(self._RECAPTCHA_IFRAME_XPATH).count() > 0:
                self.account.status = GoogleAccountStatus.CAPTCHA_REQUIRED
                raise CaptchaRequired("Обнаружена reCAPTCHA.")
            await page.locator(self._PASSWORD_FIELD_XPATH).type(self.account.password)
            await page.locator(self._PASSWORD_CONFIRMATION_BUTTON_XPATH).click()

            # Если в аккаунт с этого IP не входили ранее, то просит ввести recovery_email
            recovery_email_button = page.locator(self._RECOVERY_EMAIL_BUTTON_XPATH)
            try:
                await recovery_email_button.wait_for(timeout=self.timeout_to_wait)
                self._needs_recovery_email = True
            except TimeoutError:
                pass

            if self._needs_recovery_email:
                if not self.account.recovery_email:
                    self.account.status = GoogleAccountStatus.RECOVERY_EMAIL_REQUIRED
                    raise RecoveryEmailRequired(f"Failed to login Google account: recovery email required.")

                await recovery_email_button.click()
                await page.wait_for_load_state("load")
                await page.locator(self._RECOVERY_EMAIL_FIELD_XPATH).type(self.account.recovery_email)
                await page.locator(self._RIGHT_BUTTON_XPATH).click()
                self._needs_recovery_email = False

            await page.wait_for_load_state("load")

            try:
                await page.locator(self._RECOVERY_BUTTON_XPATH).wait_for(timeout=self.timeout_to_wait)
                self.account.status = GoogleAccountStatus.RECOVERY_REQUIRED
                raise RecoveryRequired("Failed to login Google account."
                                       " Google: We noticed unusual activity in your Google Account."
                                       " To keep your account safe, you were signed out."
                                       " To continue, you’ll need to verify it’s you.")
            except TimeoutError:
                pass

            # Иногда просит установить passkey
            # try:
            #     # TODO Проверять passkey другим способов
            #     await page.locator(self._LEFT_BUTTON_XPATH).click(timeout=self.timeout_to_wait)
            # except TimeoutError:
            #     pass

            await page.wait_for_load_state("load")

            cookies = None
            for _ in range(5):
                await page.wait_for_timeout(self.timeout_to_wait / 5)
                if any(url_pattern.search(page.url) for url_pattern in self._LOGGED_IN_URL_PATTERNS):
                    cookies = await self._context.cookies()
                    self._logged_in = are_valid_google_cookies(cookies)
                    break

            await page.close()

            if self._logged_in:
                self.account.status = GoogleAccountStatus.GOOD
                self.account.cookies = cookies
            else:
                self.account.status = GoogleAccountStatus.UNKNOWN
                raise FailedToLogin("Failed to login Google account: failed to catch auth cookies.")

        except TimeoutError:
            await page.close()
            raise FailedToLogin("Failed to login Google account: unexpected TimeoutError.")

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
        Найдите подобную ссылку: `https://accounts.google.com/o/oauth2/v2/auth?client_id=...`
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
        page = await self._new_page()

        oauth_code = None
        redirect_url = None

        async def request_handler(request: Request):
            nonlocal oauth_code
            nonlocal redirect_url

            # Поимка oauth_code и redirect_url основана на знании того, что гугл делает такой редирект:
            # https://developers.google.com/identity/protocols/oauth2/javascript-implicit-flow#redirecting
            if request.url.startswith(redirect_uri):
                redirect_url = URL(request.url)
                oauth_code = redirect_url.query.get(response_type)

        page.on("request", request_handler)

        try:
            await page.goto(oauth_url)
            # TODO Поведение страницы может отличаться, если значение prompt != "consent"
            await page.wait_for_timeout(self.timeout_to_wait)
            await page.locator(self._account_button_xpath()).click()
            await page.wait_for_load_state("networkidle")
            try:
                await page.locator(self._CONTINUE_BUTTON_XPATH).click(timeout=self.timeout_to_wait)
            except TimeoutError:
                pass
            await page.wait_for_timeout(self.timeout_to_wait)
        except TimeoutError:
            await page.close()
            raise FailedToOAuth2("Failed to OAuth2 Google account: unexpected TimeoutError.")

        await page.close()

        if not oauth_code:
            raise FailedToOAuth2("Failed to OAuth2 Google account: Failed to catch oauth code.")

        return oauth_code, str(redirect_url)
