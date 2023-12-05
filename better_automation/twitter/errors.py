from curl_cffi.requests import Response


class TwitterAPIException(Exception):
    pass


class HTTPException(TwitterAPIException):
    """
    Exception raised when an HTTP request fails

    Attributes
    ----------
    response :
        Response from the Twitter API
    api_errors :
        The errors the Twitter API responded with, if any
    api_codes :
        The error codes the Twitter API responded with, if any
    api_messages :
        The error messages the Twitter API responded with, if any
    """

    def __init__(self, response: Response, response_json: dict = None):
        self.response = response
        self.api_errors: list[dict[str, int | str]] = []
        self.api_codes: list[int] = []
        self.api_messages: list[str] = []

        if response_json is None:
            super().__init__(f"{response.status_code} {response.reason}")
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
            f"{response.status_code} {response.reason}{error_text}"
        )


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
    Exception raised for a 403 HTTP status code
    """
    pass


class NotFound(HTTPException):
    """
    Exception raised for a 404 HTTP status code
    """
    pass


class RateLimited(HTTPException):
    """
    Exception raised for a 429 HTTP status code
    """
    pass


class TwitterServerError(HTTPException):
    """
    Exception raised for a 5xx HTTP status code
    """
    pass
