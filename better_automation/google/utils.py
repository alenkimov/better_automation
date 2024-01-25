from datetime import datetime
from typing import Iterable


def check_cookies(
        cookies: list[dict],
        cookies_to_check: Iterable[str],
) -> bool:
    # Создание словаря для хранения найденных cookie
    found_cookies = {name: False for name in cookies_to_check}

    # Текущее время в формате Unix timestamp
    current_timestamp = datetime.now().timestamp()

    for cookie in cookies:
        # Если имя cookie есть в списке для проверки и его срок ещё не истёк
        if cookie['name'] in cookies_to_check:
            if 'expires' not in cookie:
                found_cookies[cookie['name']] = True
            elif current_timestamp < cookie['expires']:
                found_cookies[cookie['name']] = True

    # Проверяем, все ли нужные cookie найдены и действительны
    return all(found_cookies.values())
