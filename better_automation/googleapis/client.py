from twitter.base import BaseClient

from .models import AuthToken
from .errors import (
    HTTPException,
    BadRequest,
    Unauthorized,
    Forbidden,
    NotFound,
    GoogleAPIsServerError,
)


class GoogleAPIsClient(BaseClient):
    def __init__(self, key: str, **session_kwargs):
        super().__init__(**session_kwargs)
        self.key = key

    async def request(self, method, url, **kwargs):
        params = kwargs["params"] = kwargs.get("params") or {}
        params["key"] = self.key
        response = await self._session.request(method, url, **kwargs)
        data = response.json()

        if response.status_code == 400:
            raise BadRequest(response, data)

        if response.status_code == 401:
            raise Unauthorized(response, data)

        if response.status_code == 403:
            raise Forbidden(response, data)

        if response.status_code == 404:
            raise NotFound(response, data)

        if response.status_code >= 500:
            raise GoogleAPIsServerError(response, data)

        if not 200 <= response.status_code < 300:
            raise HTTPException(response, data)

        return response, data

    async def request_auth_data(
            self,
            provider_id: str,
            continue_uri: str,
            custom_parameter: dict = None,
    ) -> tuple[str, str]:
        """
        :return: auth_uri, session_id
        """
        url = "https://www.googleapis.com/identitytoolkit/v3/relyingparty/createAuthUri"
        payload = {
            "providerId": provider_id,
            "continueUri": continue_uri,
            "customParameter": custom_parameter if custom_parameter else {},
        }
        headers = {
            'authority': 'www.googleapis.com',
            'x-client-version': 'Chrome/Handler/2.20.2/FirebaseCore-web'
        }
        response, data = await self.request("POST", url, headers=headers, json=payload)
        return data["authUri"], data["sessionId"]

    async def sign_in(self, request_uri: str, session_id: str) -> tuple[dict, AuthToken]:
        url = "https://identitytoolkit.googleapis.com/v1/accounts:signInWithIdp"
        payload = {
            "requestUri": request_uri,
            "sessionId": session_id,
            "returnSecureToken": True,
            "returnIdpCredential": True,
        }
        headers = {
            'authority': 'identitytoolkit.googleapis.com',
            'x-client-version': 'Chrome/JsCore/10.7.1/FirebaseCore-web',
        }
        response, data = await self.request("POST", url, headers=headers, json=payload)
        auth_token = AuthToken.from_googleapis(data["idToken"], data["refreshToken"], int(data["expiresIn"]))
        return data, auth_token

    async def request_account_info(self, auth_token: str):
        url = "https://identitytoolkit.googleapis.com/v1/accounts:lookup"
        payload = {"idToken": auth_token}
        headers = {
            'authority': 'identitytoolkit.googleapis.com',
            'x-client-version': 'Chrome/JsCore/10.7.1/FirebaseCore-web',
        }
        response, data = await self.request("POST", url, headers=headers, json=payload)
        return data

    async def refresh_auth_token(self, refresh_token: str) -> tuple[dict, AuthToken]:
        url = "https://securetoken.googleapis.com/v1/token"
        payload = f"grant_type=refresh_token&refresh_token={refresh_token}"
        headers = {
            'authority': 'securetoken.googleapis.com',
            'content-type': 'application/x-www-form-urlencoded',
        }
        response, data = await self.request("POST", url, headers=headers, json=payload)
        auth_token = AuthToken.from_googleapis(data["access_token"], data["refresh_token"], data["expires_in"])
        return data, auth_token
