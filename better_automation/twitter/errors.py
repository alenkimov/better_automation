import aiohttp


class TwitterAPIException(Exception):
    pass


class HTTPException(TwitterAPIException):
    """HTTPException()

    Exception raised when an HTTP request fails

    Attributes
    ----------
    response : requests.Response | aiohttp.ClientResponse
        Requests Response from the Twitter API
    api_errors : list[dict[str, int | str]]
        The errors the Twitter API responded with, if any
    api_codes : list[int]
        The error codes the Twitter API responded with, if any
    api_messages : list[str]
        The error messages the Twitter API responded with, if any
    """

    def __init__(self, response: aiohttp.ClientResponse, response_json: dict = None):
        self.response = response
        status_code = response.status

        self.api_errors = []
        self.api_codes = []
        self.api_messages = []

        if response_json is None:
            super().__init__(f"{status_code} {response.reason}")
            return

        errors = response_json.get("errors", [])

        if "error" in response_json:
            errors.append(response_json["error"])
        else:
            errors.append(response_json)

        error_text = ""

        for error in errors:
            self.api_errors.append(error)

            if isinstance(error, str):
                self.api_messages.append(error)
                error_text += '\n' + error
                continue

            if "code" in error:
                self.api_codes.append(error["code"])
            if "message" in error:
                self.api_messages.append(error["message"])

            if "code" in error and "message" in error:
                error_text += f"\n{error['code']} - {error['message']}"
            elif "message" in error:
                error_text += '\n' + error["message"]

        if not error_text and "detail" in response_json:
            self.api_messages.append(response_json["detail"])
            error_text = '\n' + response_json["detail"]

        super().__init__(
            f"{status_code} {response.reason}{error_text}"
        )


class BadRequest(HTTPException):
    """BadRequest()

    Exception raised for a 400 HTTP status code
    """
    pass


class Unauthorized(HTTPException):
    """Unauthorized()

    Exception raised for a 401 HTTP status code
    """
    pass


class Forbidden(HTTPException):
    """Forbidden()

    Exception raised for a 403 HTTP status code
    """
    pass


class NotFound(HTTPException):
    """NotFound()

    Exception raised for a 404 HTTP status code
    """
    pass


class TooManyRequests(HTTPException):
    """TooManyRequests()

    Exception raised for a 429 HTTP status code
    """
    pass


class TwitterServerError(HTTPException):
    """TwitterServerError()

    Exception raised for a 5xx HTTP status code
    """
    pass
