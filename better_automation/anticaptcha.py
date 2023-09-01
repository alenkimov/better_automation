import asyncio
from urllib.parse import urlparse

import aiohttp
import pyuseragents


class AnticaptchaError(Exception):
    pass


class AnticaptchaClient:
    BASE_URL = "https://api.anti-captcha.com"

    def __init__(self, session: aiohttp.ClientSession, api_key: str, *, proxy: str = None, useragent: str = None):
        self._session = session
        self._api_key = api_key
        self._proxy = proxy
        self._useragent = useragent

        if self._useragent is None:
            self.set_useragent(pyuseragents.random())

    def set_useragent(self, useragent: str):
        self._useragent = useragent

    async def _request(self, method: str, payload: dict = None):
        url = f"{self.BASE_URL}/{method}"
        payload = payload.copy() if payload else {}
        payload.update({"clientKey": self._api_key})
        return await self._session.request("POST", url, json=payload)

    @staticmethod
    async def _handle_response(response: aiohttp.ClientResponse) -> dict:
        data = await response.json()
        if data == 0:
            raise AnticaptchaError
        if data["errorId"] != 0:
            raise AnticaptchaError(data["errorCode"], data["errorDescription"])
        return data

    async def request_balance(self):
        response = await self._request("getBalance")
        data = await self._handle_response(response)
        return data["balance"]

    async def _create_task(
            self,
            task_data: dict,
            *,
            proxy: str = None,
            useragent: str = None,
            cookies: str = None,
    ) -> int:
        proxy = proxy or self._proxy
        useragent = useragent or self._useragent

        if proxy and useragent:
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
                "userAgent": useragent,
            })
        if cookies: task_data.update({"cookies": cookies})
        response = await self._request("createTask", {"task": task_data})
        data = await self._handle_response(response)
        return data["taskId"]

    async def _wait_for_result(
            self,
            task_id,
            max_seconds: int = 300,
            current_second: int = 0,
            delay: int = 10
    ) -> dict:
        if current_second >= max_seconds:
            raise AnticaptchaError(f"(task_id={task_id}) Task solution expired")

        await asyncio.sleep(delay)
        response = await self._request("getTaskResult", {"taskId": task_id})
        data = await self._handle_response(response)
        match data["status"]:
            case "processing":
                return await self._wait_for_result(task_id, max_seconds, current_second + delay, delay)
            case "ready":
                return data

    async def _recaptcha_task(self, task_type, url: str, site_key: str, task_data: dict = None, **kwargs) -> str:
        task_data = task_data.copy() if task_data else {}
        task_data.update({
            "type": task_type,
            "websiteURL": url,
            "websiteKey": site_key,
        })
        task_id = await self._create_task(task_data, **kwargs)
        data = await self._wait_for_result(task_id)
        return data["solution"]["gRecaptchaResponse"]

    async def recaptcha_v2(
            self,
            url: str,
            site_key: str,
            *,
            is_invisible: bool = False,
            recaptcha_data_s: str = None,
            **kwargs,
    ) -> str:
        task_type = "RecaptchaV2Task" if kwargs.get("proxy") is not None else "RecaptchaV2TaskProxyless"
        task_data = {
            "isInvisible": is_invisible,
        }
        if recaptcha_data_s:
            task_data["recaptchaDataSValue"] = recaptcha_data_s
        return await self._recaptcha_task(task_type, url, site_key, task_data, **kwargs)

    async def hcaptcha(
            self,
            url: str,
            site_key: str,
            **kwargs,
    ) -> str:
        task_type = "HCaptchaTask" if kwargs.get("proxy") is not None else "HCaptchaTaskProxyless"
        return await self._recaptcha_task(task_type, url, site_key, **kwargs)

    async def _report_incorrect_captcha(self, task_id, report_method: str):
        return await self._request(report_method, {"taskId": task_id})

    async def report_incorrect_image_captcha(self, task_id):
        return await self._report_incorrect_captcha(task_id, "reportIncorrectImageCaptcha")

    async def report_incorrect_recaptcha(self, task_id):
        return await self._report_incorrect_captcha(task_id, "reportIncorrectRecaptcha")

    async def report_correct_recaptcha(self, task_id):
        return await self._report_incorrect_captcha(task_id, "reportCorrectRecaptcha")
