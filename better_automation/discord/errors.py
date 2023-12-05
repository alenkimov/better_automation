from typing import Any, Union

from curl_cffi import requests


class DiscordException(Exception):
    """Base exception class for discord.py

    Ideally speaking, this could be caught to handle any exceptions raised from this library.
    """

    pass


def _flatten_error_dict(d: dict[str, Any], key: str = '') -> dict[str, str]:
    items: list[tuple[str, str]] = []
    for k, v in d.items():
        new_key = key + '.' + k if key else k

        if isinstance(v, dict):
            try:
                _errors: list[dict[str, Any]] = v['_errors']
            except KeyError:
                items.extend(_flatten_error_dict(v, new_key).items())
            else:
                items.append((new_key, ' '.join(x.get('message', '') for x in _errors)))
        else:
            items.append((new_key, v))

    return dict(items)


class HTTPException(DiscordException):
    """Exception that's raised when an HTTP request operation fails.

    Attributes
    ------------
    response:
        The response of the failed HTTP request.

    text:
        The text of the error. Could be an empty string.
    status:
        The status code of the HTTP request.
    code:
        The Discord specific error code for the failure.
    """

    def __init__(self, response: requests.Response, message: str | dict[str, Any] | None):
        self.response = response
        self.status: int = response.status_code
        self.code: int
        self.text: str
        if isinstance(message, dict):
            self.code = message.get('code', 0)
            base = message.get('message', '')
            errors = message.get('errors')
            self._errors: dict[str, Any] = errors
            if errors:
                errors = _flatten_error_dict(errors)
                helpful = '\n'.join('In %s: %s' % t for t in errors.items())
                self.text = base + '\n' + helpful
            else:
                self.text = base
        else:
            self.text = message or ''
            self.code = 0

        error_message = f"{self.response.status_code} {self.response.reason} ({self.code})"
        if len(self.text):
            error_message = f"{error_message}: {self.text}"

        super().__init__(error_message)


class CaptchaRequired(DiscordException):
    """Exception that's raised for when status code 400 occurs
    and captcha bypass required.
    """

    def __init__(self, response: requests.Response, data: dict[str, Any]):
        self.response = response
        self.status = response.status_code
        self._data = data
        self.sitekey = data["captcha_sitekey"]
        self.rqdata = data["captcha_rqdata"]
        self.rqtoken = data["captcha_rqtoken"]
        self.service = data["captcha_service"]

        error_message = (f"You need to solve {self.service} to perform this action."
                         f"\tUse sitekey, rqdata, rqtoken to solve it.")
        super().__init__(error_message)


class BadRequest(HTTPException):
    """
    Exception raised for a 400 HTTP status code
    """
    pass


class Unauthorized(HTTPException):
    """
    Exception raised for a 401 HTTP status code
    """
    pass


class Forbidden(HTTPException):
    """
    Exception that's raised for when status code 403 occurs.
    """
    pass


class NotFound(HTTPException):
    """
    Exception that's raised for when status code 404 occurs.
    """
    pass


class RateLimited(DiscordException):
    """Exception that's raised for when status code 429 occurs
    and the timeout is greater than the configured maximum using
    the ``max_ratelimit_timeout`` parameter in :class:`Client`.

    This is not raised during global ratelimits.

    Attributes
    ------------
    retry_after:
        The amount of seconds that the client should wait before retrying
        the request.
    """

    def __init__(self, retry_after: float):
        self.retry_after = retry_after
        super().__init__(f'Too many requests. Retry in {retry_after:.2f} seconds.')


class DiscordServerError(HTTPException):
    """
    Exception that's raised for when a 500 range status code occurs.
    """
    pass
