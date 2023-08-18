from functools import wraps

import aiohttp
from aiohttp.client_exceptions import ContentTypeError

from .errors import (
    FailedToObtainCT0,
    HTTPException,
    BadRequest,
    Unauthorized,
    Forbidden,
    NotFound,
    TooManyRequests,
    TwitterServerError,
)
from ..http_client import BetterClientSession


class TwitterAPIError(Exception):
    def __init__(self, errors: list[dict]):
        self.errors = errors
        super().__init__(str(self.errors))


class TwitterAPI(BetterClientSession):
    DEFAULT_HEADERS = {
        'authority': 'twitter.com',
        'accept': '*/*',
        'accept-language': 'uk',
        'authorization': 'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA',
        'content-type': 'application/json',
        'origin': 'https://twitter.com',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'x-twitter-active-user': 'yes',
        'x-twitter-auth-type': 'OAuth2Session',
        'x-twitter-client-language': 'en',
    }
    queryId_like = 'lI07N6Otwv1PhnEgXILM7A'
    queryId_retweet = 'ojPdsZsimiJrUGLR1sjUtA'
    queryId_create_tweet = 'SoVnbfCycZ7fERGCwpZkYA'
    queryId_handler_converter = '9zwVLJ48lmVUk8u_Gh9DmA'
    queryId_tweet_parser = 'Uuw5X2n3tuGE_SatnXUqLA'
    queryId_tweet_details = 'VWFGPVAGkZMGRKGe3GFFnA'
    base_url = 'https://twitter.com/i/api/graphql/'

    def __init__(self, auth_token: str, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.headers.update(self.DEFAULT_HEADERS)
        self._auth_token = None
        self._ct0 = None
        self.set_auth_token(auth_token)
        self.set_ct0("")

    def set_auth_token(self, auth_token: str):
        self._auth_token = auth_token
        self.cookie_jar.update_cookies({"auth_token": auth_token})

    def set_ct0(self, ct0: str):
        self._ct0 = ct0
        self.headers["x-csrf-token"] = ct0
        self.cookie_jar.update_cookies({"ct0": ct0})

    @property
    def auth_token(self) -> str | None:
        return self._auth_token

    @property
    def ct0(self) -> str | None:
        return self._ct0

    async def _request(self, *args, **kwargs) -> aiohttp.ClientResponse:
        response = await super()._request(*args, **kwargs)

        try:
            response_json = await response.json()
        except aiohttp.client_exceptions.ContentTypeError:
            response_json = None

        if response.status == 400:
            raise BadRequest(response, response_json)
        if response.status == 401:
            raise Unauthorized(response, response_json)
        if response.status == 403:
            raise Forbidden(response, response_json)
        if response.status == 404:
            raise NotFound(response, response_json)
        if response.status == 429:
            raise TooManyRequests(response, response_json)
        if response.status >= 500:
            raise TwitterServerError(response, response_json)
        if not 200 <= response.status < 300:
            raise HTTPException(response, response_json)

        return response

    async def _request_ct0(self) -> str:
        url = 'https://twitter.com/i/api/2/oauth2/authorize'
        try:
            response = await self.get(url)
            if "ct0" in response.cookies:
                return response.cookies["ct0"].value
            else:
                raise FailedToObtainCT0("Failed to obtain ct0")
        except Forbidden as e:
            if "ct0" in e.response.cookies:
                return e.response.cookies["ct0"].value
            else:
                raise

    @staticmethod
    def ensure_ct0(coro):
        @wraps(coro)
        async def wrapper(self, *args, **kwargs):
            if not self.ct0:
                self.set_ct0(await self._request_ct0())
            return await coro(self, *args, **kwargs)
        return wrapper

    @ensure_ct0
    async def _request_bind_code(
            self,
            client_id: str,
            code_challenge: str,
            state: str,
            code_challenge_method: str = "plain",
            scope: str = "tweet.read users.read follows.read offline.access like.read",
            response_type: str = "code",
    ):
        url = "https://twitter.com/i/api/2/oauth2/authorize"
        querystring = {
            "client_id": client_id,
            "code_challenge": code_challenge,
            "code_challenge_method": code_challenge_method,
            "state": state,
            "scope": scope,
            "response_type": response_type,
        }
        response = await self.request("GET", url, params=querystring)
        data = await response.json()
        code = data["auth_code"]
        return code

    @ensure_ct0
    async def _post_authorise(self, bind_code: str):
        data = {
            'approval': 'true',
            'code': bind_code,
        }
        headers = {'content-type': 'application/x-www-form-urlencoded'}
        await self.post('https://twitter.com/i/api/2/oauth2/authorize', headers=headers, data=data)

    async def bind_app(self, *args, **kwargs):
        bind_code = await self._request_bind_code(*args, **kwargs)
        await self._post_authorise(bind_code)
        return bind_code

    @ensure_ct0
    async def request_username(self) -> str:
        url = 'https://api.twitter.com/1.1/account/settings.json'
        params = {
            'include_mention_filter': 'true',
            'include_nsfw_user_flag': 'true',
            'include_nsfw_admin_flag': 'true',
            'include_ranked_timeline': 'true',
            'include_alt_text_compose': 'true',
            'ext': 'ssoConnections',
            'include_country_code': 'true',
            'include_ext_dm_nsfw_media_filter': 'true',
            'include_ext_sharing_audiospaces_listening_data_with_followers': 'true',
        }
        del self.headers['content-type']
        response = await self.get(url, params=params)
        response_data: dict = await response.json()
        username = response_data.get("screen_name")
        return username
