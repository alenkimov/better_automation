import asyncio
import time

from twitter.base import BaseClient

from .errors import SmsServiceError


class SmshubClient(BaseClient):
    BASE_API_URL = "https://smshub.org/stubs/handler_api.php"
    UNOFFICIAL_API_URL = "https://smshub.org/api.php"

    def __init__(self, key: str, **session_kwargs):
        super().__init__(**session_kwargs)
        self.key = key

    async def _request(self, method: str, url: str, **kwargs):
        params = kwargs["params"] = kwargs.get("params") or {}
        params["api_key"] = self.key
        response = await self._session.request(method, url, **kwargs)

        if response.text.startswith('ERROR'):
            raise SmsServiceError(response.text)

        return response

    async def request_balance(self) -> float:
        """https://smshub.org/ru/info#getBalance"""
        params = {'action': 'getBalance'}
        response = await self._request("GET", self.BASE_API_URL, params=params)

        _, balance_str = response.text.split(':')
        balance_float = float(balance_str)
        return balance_float

    async def request_numbers_status(self, country: str = None, operator: str = None) -> dict:
        params = {'action': 'getNumbersStatus'}
        if country:
            params['country'] = country
        if operator:
            params['operator'] = operator
        response = await self._request("GET", self.BASE_API_URL, params=params)
        return response.json()

    async def request_number(
            self,
            service: str,
            country: str = None,
            operator: str = None,
            forward: int = 0,
    ) -> tuple[int, int]:
        """
        https://smshub.org/ru/info#getNumbers
        :return: id, number
        """
        params = {
            'action': 'getNumber',
            'service': service,
            'forward': forward
        }
        if country:
            params['country'] = country
        if operator:
            params['operator'] = operator
        response = await self._request("GET", self.BASE_API_URL, params=params)

        if response.text == "NO_NUMBERS":
            raise SmsServiceError(response.text)

        _, id, number = response.text.split(':')
        return int(id), number

    async def _set_status(self, id: str, status: int) -> str:
        """
        https://smshub.org/ru/info#setStatus

        Сразу после получения номера доступны следующие действия:
        8 - Отменить активацию
        1 - Сообщить, что SMS отправлена (необязательно)
        Для активации со статусом 1:
        8 - Отменить активацию
        Сразу после получения кода:
        3 - Запросить еще одну смс
        6 - Подтвердить SMS-код и завершить активацию
        Для активации со статусом 3:
        6 - Подтвердить SMS-код и завершить активацию

        Выходные данные
        Ответ сервера	Описание
        ACCESS_READY	Готовность ожидания смс
        ACCESS_RETRY_GET	Ожидаем новое смс
        ACCESS_ACTIVATION	Активация успешно завершена
        ACCESS_CANCEL	Активация отменена
        """
        params = {
            'action': 'setStatus',
            'id': id,
            'status': status
        }
        response = await self._request("GET", self.BASE_API_URL, params=params)
        return response.text

    async def request_another_sms(self, id):
        await self._set_status(id, 3)

    async def confirm_activation(self, id):
        await self._set_status(id, 6)

    async def cancel_activation(self, id):
        await self._set_status(id, 8)

    async def request_status(self, id: str) -> str:
        """https://smshub.org/ru/info#getStatus"""
        params = {
            'action': 'getStatus',
            'id': id
        }
        response = await self._request("GET", self.BASE_API_URL, params=params)
        return response.text

    async def request_list_of_countries_and_operators(self):
        params = {
            'cat': 'scripts',
            'act': 'manageActivations',
            'asc': 'getListOfCountriesAndOperators'
        }
        response = await self._request("POST", self.UNOFFICIAL_API_URL, params=params)

        return response.json()

    async def wait_for_code(self, id: int, delay: int = 10, max_wait_time: int = 300) -> str:
        await self._set_status(id, 1)  # Сообщаю о том, что сообщение отправлено
        start_time = time.time()  # Засекаем начальное время

        while True:
            response = await self.request_status(id)
            print(response)
            if response.startswith("STATUS_OK"):
                status, code = response.split(":")
                await self.confirm_activation(id)  # Подтверждаю получение кода
                return code

            if (time.time() - start_time) > max_wait_time:
                # Время ожидания превысило максимально допустимое, прерываем цикл
                raise TimeoutError("Max wait time exceeded")

            await asyncio.sleep(delay)

    async def request_prices(self, service: str, country: str = None) -> dict:
        params = {'action': 'getPrices', 'service': service}
        if country:
            params['country'] = country
        response = await self._request("GET", self.BASE_API_URL, params=params)
        return response.json()

    async def set_max_price(self, service: str, max_price: float, country: str) -> str:
        params = {
            'action': 'setMaxPrice',
            'service': service,
            'maxPrice': max_price,
            'country': country
        }
        response = await self._request("GET", self.BASE_API_URL, params=params)
        return response.text

    async def request_current_activations(self) -> dict:
        params = {'action': 'getCurrentActivations'}
        response = await self._request("GET", self.BASE_API_URL, params=params)
        return response.json()
