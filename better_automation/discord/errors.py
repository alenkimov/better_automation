from typing import Any

from curl_cffi import requests


__all__ = [
    "DiscordException",
    "HTTPException",
    "BadRequest",
    "CaptchaRequired",
    "Unauthorized",
    "Forbidden",
    "NotFound",
    "RateLimited",
    "DiscordServerError",
]


class DiscordException(Exception):
    pass


def _flatten_error_dict(d: dict[str, Any], key: str = "") -> dict[str, str]:
    items: list[tuple[str, str]] = []
    for k, v in d.items():
        new_key = key + '.' + k if key else k

        if isinstance(v, dict):
            try:
                _errors: list[dict[str, Any]] = v["_errors"]
            except KeyError:
                items.extend(_flatten_error_dict(v, new_key).items())
            else:
                items.append((new_key, " ".join(x.get("message", "") for x in _errors)))
        else:
            items.append((new_key, v))

    return dict(items)


class HTTPException(DiscordException):
    """Exception that's raised when an HTTP request operation fails
    """

    def __init__(
            self,
            response: requests.Response,
            data: str | dict[str, Any] | None,
            custom_exception_message: str = None,
    ):
        self.response = response
        if isinstance(data, dict):
            self.code = data.get("code", 0)
            base = data.get("message", "")
            errors = data.get('errors')
            self._errors: dict[str, Any] = errors
            if errors:
                errors = _flatten_error_dict(errors)
                helpful = "\n".join("In %s: %s" % t for t in errors.items())
                self.text = base + '\n' + helpful
            else:
                self.text = base
        else:
            self.text = data or ""
            self.code = 0

        exception_message = f"{self.response.status_code} ({self.code})"
        if len(self.text):
            exception_message = f"{exception_message}: {self.text}"
        super().__init__(custom_exception_message or exception_message)


class BadRequest(HTTPException):
    """Exception raised for a 400 HTTP status code.
    """
    pass


class CaptchaRequired(BadRequest):
    """Exception raised for a 400 HTTP status code and captcha bypass required.
    """

    def __init__(self, response: requests.Response, data: dict[str, Any]):
        self.sitekey = data["captcha_sitekey"]
        self.rqdata = data["captcha_rqdata"]
        self.rqtoken = data["captcha_rqtoken"]
        self.service = data["captcha_service"]
        super().__init__(
            response, data,
            custom_exception_message=f"You need to solve {self.service} to perform this action."
                                     f"\nBinding a phone number can reduce the chance of captchas appearing.",
        )


class Unauthorized(HTTPException):
    """Exception raised for a 401 HTTP status code.
    """
    pass


class Forbidden(HTTPException):
    """Exception raised for a 403 HTTP status code.
    """
    pass


class NotFound(HTTPException):
    """Exception raised for a 404 HTTP status code.
    """
    pass


class RateLimited(HTTPException):
    """Exception raised for a 429 HTTP status code.

    Attributes
    ------------
    retry_after:
        The amount of seconds that the client should wait before retrying
        the request.
    """

    def __init__(
            self,
            response: requests.Response,
            data: str | dict[str, Any] | None,
    ):
        self.retry_after = data["retry_after"]
        super().__init__(
            response, data,
            custom_exception_message=f"Rate limited. Retry in {self.retry_after:.2f} seconds.",
        )


class DiscordServerError(HTTPException):
    """Exception raised for a 5xx HTTP status code.
    """
    pass
