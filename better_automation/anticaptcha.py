import asyncio
from urllib.parse import urlparse
import aiohttp


class AnticaptchaError(Exception):
    pass


class AnticaptchaClient:
    BASE_URL = "https://api.anti-captcha.com"
    DEFAULT_HEADERS = {"Content-Type": "application/json",
                       "Accept": "application/json"}

    def __init__(self, session: aiohttp.ClientSession, api_key: str):
        self._session = session
        self.api_key = api_key
        self.is_invisible = 0

    async def request(self, method: str, payload: dict = None):
        url = f"{self.BASE_URL}/{method}"
        payload = payload.copy() if payload else {}
        payload.update({"clientKey": self.api_key})
        print(f"Request data: {method} {payload}")
        return await self._session.request("POST", url, json=payload)

    @staticmethod
    async def handle_response(response: aiohttp.ClientResponse) -> dict:
        data = await response.json()
        print(f"Answer: {data}")
        if data == 0:
            raise AnticaptchaError
        if data["errorId"] != 0:
            raise AnticaptchaError(data["errorCode"], data["errorDescription"])
        return data

    async def request_balance(self):
        response = await self.request("getBalance")
        data = await self.handle_response(response)
        return data["balance"]

    async def create_task(
            self,
            task_data: dict,
            *,
            proxy: str = None,
            user_agent: str = None,
            cookies: str = None,
    ) -> int:
        if proxy and not user_agent:
            raise ValueError(f"Because you use proxy an user_agent is required")

        if proxy:
            parsed_url = urlparse(proxy)
            proxy_type = parsed_url.scheme
            proxy_address = parsed_url.hostname
            proxy_port = parsed_url.port
            proxy_login = parsed_url.username
            proxy_password = parsed_url.password
            task_data.update({
                "proxyType": proxy_type,
                "proxyAddress": proxy_address,
                "proxyPort": proxy_port,
                "proxyLogin": proxy_login,
                "proxyPassword": proxy_password,
            })
        if user_agent: task_data.update({"userAgent": user_agent})
        if cookies: task_data.update({"cookies": cookies})

        response = await self.request("createTask", {"task": task_data})
        data = await self.handle_response(response)
        return data["taskId"]

    async def wait_for_result(
            self,
            task_id,
            max_seconds: int = 300,
            current_second: int = 0,
            delay: int = 10
    ) -> dict:
        if current_second >= max_seconds:
            raise AnticaptchaError(f"(task_id={task_id}) Task solution expired")

        await asyncio.sleep(delay)
        response = await self.request("getTaskResult", {"taskId": task_id})
        data = await self.handle_response(response)
        match data["status"]:
            case "processing":
                return await self.wait_for_result(task_id, max_seconds, current_second + delay, delay)
            case "ready":
                return data

    async def report_incorrect_image_captcha(self, task_id):
        return await self.request("reportIncorrectImageCaptcha", {"taskId": task_id})

    async def report_incorrect_recaptcha(self, task_id):
        return await self.request("reportIncorrectRecaptcha", {"taskId": task_id})

    async def report_correct_recaptcha(self, task_id):
        return await self.request("reportCorrectRecaptcha", {"taskId": task_id})

    async def recaptcha_v2(
            self,
            url: str,
            site_key: str,
            *,
            is_invisible: bool = False,
            recaptcha_data_s: str = None,
            **kwargs,
    ) -> str:
        task_type = "RecaptchaV2Task" if "proxy" in kwargs else "RecaptchaV2TaskProxyless"
        task_data = {
            "type": task_type,
            "websiteURL": url,
            "websiteKey": site_key,
            "isInvisible": is_invisible,
        }
        if recaptcha_data_s:
            task_data["recaptchaDataSValue"] = recaptcha_data_s
        task_id = await self.create_task(task_data, **kwargs)
        data = await self.wait_for_result(task_id)
        return data["solution"]["gRecaptchaResponse"]
