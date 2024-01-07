from curl_cffi import requests


__all__ = [
    "GoogleAPIsException",
    "HTTPException",
    "BadRequest",
    "Unauthorized",
    "Forbidden",
    "NotFound",
    "GoogleAPIsServerError",
]


class GoogleAPIsException(Exception):
    pass


class HTTPException(GoogleAPIsException):
    """Exception that's raised when an HTTP request operation fails
    """

    def __init__(
            self,
            response: requests.Response,
            data: dict,
            custom_exception_message: str = None,
    ):
        self.response = response
        error_data = data["error"]
        self.message = error_data["message"]
        self.error_list = error_data["errors"]

        exception_message = f"{self.response.status_code} {self.message}"
        super().__init__(custom_exception_message or exception_message)


class BadRequest(HTTPException):
    """Exception raised for a 400 HTTP status code.
    """
    pass


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


class GoogleAPIsServerError(HTTPException):
    """Exception raised for a 5xx HTTP status code.
    """
    pass
