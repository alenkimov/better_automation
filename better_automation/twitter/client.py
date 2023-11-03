import asyncio
import time
from functools import wraps
from typing import Any

import aiohttp
from aiohttp import MultipartWriter

from async_lru import alru_cache

from .errors import (
    HTTPException,
    BadRequest,
    Unauthorized,
    Forbidden,
    NotFound,
    TooManyRequests,
    TwitterServerError,
)
from ..utils import to_json
from .account import Account, AccountStatus
from .models import UserData

async_cache = alru_cache(maxsize=None)


def remove_at_sign(username: str) -> str:
    if username.startswith("@"):
        return username[1:]
    return username


class Client:
    DEFAULT_HEADERS = {
        'authority': 'twitter.com',
        'accept': '*/*',
        'accept-language': 'uk',
        'authorization': 'Bearer AAAAAAAAAAAAAAAAAAAAANRILgAAAAAAnNwIzUejRCOuH5E6I8xnZz4puTs%3D1Zv7ttfk8LF81IUq16cHjhLTvJu4FA33AGWWjCpTnA',
        'origin': 'https://twitter.com',
        'sec-ch-ua-mobile': '?0',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'x-twitter-active-user': 'yes',
        'x-twitter-auth-type': 'OAuth2Session',
        'x-twitter-client-language': 'en',
    }
    GRAPHQL_URL = 'https://twitter.com/i/api/graphql'
    ACTION_TO_QUERY_ID = {
        'CreateRetweet': "ojPdsZsimiJrUGLR1sjUtA",
        'FavoriteTweet': "lI07N6Otwv1PhnEgXILM7A",
        'UnfavoriteTweet': "ZYKSe-w7KEslx3JhSIk5LA",
        'CreateTweet': "SoVnbfCycZ7fERGCwpZkYA",
        'TweetResultByRestId': "V3vfsYzNEyD9tsf4xoFRgw",
        'ModerateTweet': "p'jF:GVqCjTcZol0xcBJjw",
        'DeleteTweet': "VaenaVgh5q5ih7kvyVjgtg",
        'UserTweets': "Uuw5X2n3tuGE_SatnXUqLA",
        'TweetDetail': 'VWFGPVAGkZMGRKGe3GFFnA',
        'ProfileSpotlightsQuery': '9zwVLJ48lmVUk8u_Gh9DmA',
        'Following': 't-BPOrMIduGUJWO_LxcvNQ',
        'Followers': '3yX7xr2hKjcZYnXt6cU6lQ',
        'UserByScreenName': 'G3KGOASz96M-Qu0nwmGXNg',
    }

    @classmethod
    def _action_to_url(cls, action: str) -> tuple[str, str]:
        """Returns url and query_id"""
        query_id = cls.ACTION_TO_QUERY_ID[action]
        url = f"{cls.GRAPHQL_URL}/{query_id}/{action}"
        return url, query_id

    def __init__(
            self,
            account: Account,
            session: aiohttp.ClientSession,
            *,
            wait_on_rate_limit: bool = True,
    ):
        """
        Инициализирует клиент с заданным аккаунтом и сессией.

        Args:
            account (Account): Экземпляр аккаунта, используемый для аутентификации.
            session (aiohttp.ClientSession): Сессия клиента для выполнения асинхронных HTTP-запросов.
            wait_on_rate_limit (bool): Флаг, определяющий, следует ли ожидать сброса лимита запросов.
        """

        self.account = account
        self.session = session
        self.wait_on_rate_limit = wait_on_rate_limit

    async def request(
            self,
            method,
            url,
            params: dict = None,
            headers: dict = None,
            json: Any = None,
            data: Any = None,
    ) -> tuple[aiohttp.ClientResponse, Any]:
        """
        Выполняет асинхронный HTTP-запрос с использованием предоставленных параметров и обрабатывает ответ.

        Args:
            method: HTTP-метод запроса.
            url: URL-адрес запроса.
            params (dict): Параметры строки запроса.
            headers (dict): Заголовки запроса.
            json: Тело запроса в формате JSON.
            data: Данные запроса.

        Returns:
            tuple[aiohttp.ClientResponse, Any]: Ответ сервера и данные в формате JSON.

        Raises:
            HTTPException: Общее исключение для HTTP-ошибок.
            BadRequest: Исключение для статуса HTTP 400.
            Unauthorized: Исключение для статуса HTTP 401.
            Forbidden: Исключение для статуса HTTP 403.
            NotFound: Исключение для статуса HTTP 404.
            TooManyRequests: Исключение для статуса HTTP 429.
            TwitterServerError: Исключение для серверных ошибок Twitter с кодом статуса >= 500.
        """

        cookies = {"auth_token": self.account.auth_token}
        full_headers = headers or {}
        full_headers.update(self.DEFAULT_HEADERS)

        if self.account.ct0:
            cookies["ct0"] = self.account.ct0
            full_headers["x-csrf-token"] = self.account.ct0

        async with self.session.request(
                method, url,
                params=params,
                json=json,
                headers=full_headers,
                cookies=cookies,
                data=data,
        ) as response:
            await response.read()

        response_json = await response.json()

        if response.status == 400:
            raise BadRequest(response, response_json)
        if response.status == 401:
            exc = Unauthorized(response, response_json)

            if 32 in exc.api_codes:
                self.account.status = AccountStatus.BAD_TOKEN

            raise exc
        if response.status == 403:
            exc = Forbidden(response, response_json)

            if 353 in exc.api_codes and "ct0" in response.cookies:
                self.account.ct0 = response.cookies["ct0"].value
                return await self.request(
                    method, url, params, headers, json, data,
                )

            if 64 in exc.api_codes:
                self.account.status = AccountStatus.SUSPENDED

            if 326 in exc.api_codes:
                self.account.status = AccountStatus.LOCKED

            raise exc
        if response.status == 404:
            raise NotFound(response, response_json)
        if response.status == 429:
            if self.wait_on_rate_limit:
                reset_time = int(response.headers["x-rate-limit-reset"])
                sleep_time = reset_time - int(time.time()) + 1
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                return await self.request(
                    method, url, params, headers, json, data,
                )
            else:
                raise TooManyRequests(response, response_json)
        if response.status >= 500:
            raise TwitterServerError(response, response_json)
        if not 200 <= response.status < 300:
            raise HTTPException(response, response_json)

        if "errors" in response_json:
            exc = HTTPException(response, response_json)

            if 141 in exc.api_codes:
                self.account.status = AccountStatus.SUSPENDED

            if 326 in exc.api_codes:
                self.account.status = AccountStatus.LOCKED

            raise exc

        self.account.status = AccountStatus.GOOD
        return response, response_json

    async def _request_bind_code(
            self,
            client_id: str,
            code_challenge: str,
            state: str,
            redirect_uri: str,
            code_challenge_method: str,
            scope: str,
            response_type: str,
    ):
        """
        Запрашивает код привязки для OAuth аутентификации.

        Args:
            client_id (str): Идентификатор клиента OAuth.
            code_challenge (str): Параметр для метода проверки подлинности PKCE.
            state (str): Состояние CSRF-защиты.
            redirect_uri (str): URI перенаправления после аутентификации.
            code_challenge_method (str): Метод генерации code_challenge.
            scope (str): Запрашиваемые разрешения.
            response_type (str): Тип ответа в запросе OAuth.

        Returns:
            str: Код привязки.
        """

        url = "https://twitter.com/i/api/2/oauth2/authorize"
        querystring = {
            "client_id": client_id,
            "code_challenge": code_challenge,
            "code_challenge_method": code_challenge_method,
            "state": state,
            "scope": scope,
            "response_type": response_type,
            "redirect_uri": redirect_uri,
        }
        response, response_json = await self.request("GET", url, params=querystring)
        bind_code = response_json["auth_code"]
        return bind_code

    async def _confirm_binding(self, bind_code: str):
        """
        Подтверждает привязку приложения.

        Args:
            bind_code (str): Код привязки для подтверждения.
        """

        data = {
            'approval': 'true',
            'code': bind_code,
        }
        headers = {'content-type': 'application/x-www-form-urlencoded'}
        await self.request("POST", 'https://twitter.com/i/api/2/oauth2/authorize', headers=headers, data=data)

    async def bind_app(
            self,
            client_id: str,
            code_challenge: str,
            state: str,
            redirect_uri: str,
            code_challenge_method: str,
            scope: str,
            response_type: str,
    ):
        """
        Привязка приложения.

        Args:
            client_id (str): Идентификатор клиента OAuth.
            code_challenge (str): Параметр для метода проверки подлинности PKCE.
            state (str): Состояние CSRF-защиты.
            redirect_uri (str): URI перенаправления после аутентификации.
            code_challenge_method (str): Метод генерации code_challenge.
            scope (str): Запрашиваемые разрешения.
            response_type (str): Тип ответа в запросе OAuth.

        Returns:
            str: Код подтверждения привязки.
        """

        bind_code = await self._request_bind_code(
            client_id, code_challenge, state, redirect_uri, code_challenge_method, scope, response_type,
        )
        await self._confirm_binding(bind_code)
        return bind_code

    @async_cache
    async def _request_username(self) -> str:
        """Запрашивает имя пользователя."""

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
        response, response_json = await self.request("GET", url, params=params)
        username = response_json['screen_name']
        return username

    @async_cache
    async def _profile_spotlight_query(self, username: str) -> dict:
        """Раньше использовался для запроса ID пользователя. Сейчас не используется."""
        url, query_id = self._action_to_url('ProfileSpotlightsQuery')
        params = {'variables': to_json({"screen_name": username})}
        response, response_json = await self.request("GET", url, params=params)
        return response_json

    async def _request_user_data(self, username: str) -> UserData:
        url, query_id = self._action_to_url('UserByScreenName')
        variables = {
            "screen_name": username,
            "withSafetyModeUserFields": True,
        }
        features = {
            "hidden_profile_likes_enabled": True,
            "hidden_profile_subscriptions_enabled": True,
            "responsive_web_graphql_exclude_directive_enabled": True,
            "verified_phone_label_enabled": False,
            "subscriptions_verification_info_is_identity_verified_enabled": True,
            "subscriptions_verification_info_verified_since_enabled": True,
            "highlights_tweets_tab_ui_enabled": True,
            "creator_subscriptions_tweet_preview_api_enabled": True,
            "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
            "responsive_web_graphql_timeline_navigation_enabled": True,
        }
        field_toggles = {
            "withAuxiliaryUserLabels": False,
        }
        params = {
            "variables": to_json(variables),
            "features": to_json(features),
            "fieldToggles": to_json(field_toggles),
        }
        response, response_json = await self.request("GET", url, params=params)
        user_data_dict = response_json['data']['user']['result']
        return UserData(user_data_dict)

    async def request_user_data(self, username: str = None) -> UserData | None:
        if username:
            user_data = await self._request_user_data(remove_at_sign(username))
            return user_data
        else:
            username = self.account.data.username if self.account.data else await self._request_username()
            user_data = await self._request_user_data(username)
            self.account.data = user_data

    async def _upload_image_init(self, total_bytes) -> dict:
        params = {
            'command': 'INIT',
            'total_bytes': total_bytes,
            'media_type': 'image/jpeg',
            # 'media_category': 'tweet_image',
        }
        response, response_json = await self.request("POST", 'https://upload.twitter.com/i/media/upload.json', params=params)
        return response_json

    async def _upload_image_append(self, media_id: int, image_as_bytes: bytes):
        url = 'https://upload.twitter.com/i/media/upload.json'
        params = {
            'command': 'APPEND',
            'media_id': str(media_id),
            'segment_index': '0',
        }
        await self.request("OPTIONS", url, params=params)
        writer = MultipartWriter(boundary='----WebKitFormBoundaryCGqmEUMuU9BgPiZm')
        part = writer.append(image_as_bytes)
        part.set_content_disposition('form-data', name="media", filename="blob")
        part.headers['Content-Type'] = 'application/octet-stream'
        headers = {'content-type': writer.headers['Content-Type']}
        await self.request("POST", url, headers=headers, params=params, data=writer)

    async def _upload_image_finalize(self, media_id):
        url = 'https://upload.twitter.com/i/media/upload.json'
        params = {
            'command': 'FINALIZE',
            'media_id': str(media_id),
            # 'original_md5': '52fe60fa015d5fd58a4b3a98fdd4d54g',
        }
        await self.request("POST", url, params=params)

    async def upload_image(self, image: bytes) -> str:
        """Upload image as bytes. Returns media_id"""
        media_data = await self._upload_image_init(len(image))
        media_id = media_data['media_id_string']
        await self._upload_image_append(media_id, image)
        await self._upload_image_finalize(media_id)
        return media_id

    async def _follow_action(self, action: str, user_id: int | str) -> bool:
        url = f"https://twitter.com/i/api/1.1/friendships/{action}.json"
        params = {
            'include_profile_interstitial_type': '1',
            'include_blocking': '1',
            'include_blocked_by': '1',
            'include_followed_by': '1',
            'include_want_retweets': '1',
            'include_mute_edge': '1',
            'include_can_dm': '1',
            'include_can_media_tag': '1',
            'include_ext_has_nft_avatar': '1',
            'include_ext_is_blue_verified': '1',
            'include_ext_verified_type': '1',
            'include_ext_profile_image_shape': '1',
            'skip_status': '1',
            'user_id': user_id,
        }
        headers = {
            'content-type': 'application/x-www-form-urlencoded',
        }
        response, response_json = await self.request("POST", url, params=params, headers=headers)
        return "id" in response_json

    async def follow(self, user_id: str | int) -> bool:
        return await self._follow_action("create", user_id)

    async def unfollow(self, user_id: str | int) -> bool:
        return await self._follow_action("destroy", user_id)

    async def _interact_with_tweet(self, action: str, tweet_id: int) -> dict:
        url, query_id = self._action_to_url(action)
        json_payload = {
            'variables': {
                'tweet_id': tweet_id,
                'dark_request': False
            },
            'queryId': query_id
        }
        response, response_json = await self.request("POST", url, json=json_payload)
        return response_json

    async def repost(self, tweet_id: int) -> int:
        """Repost (retweet) a tweet by its id"""
        response_json = await self._interact_with_tweet('CreateRetweet', tweet_id)
        retweet_id = int(response_json['data']['create_retweet']['retweet_results']['result']['rest_id'])
        return retweet_id

    async def like(self, tweet_id: int) -> bool:
        response_json = await self._interact_with_tweet('FavoriteTweet', tweet_id)
        is_liked = response_json['data']['favorite_tweet'] == 'Done'
        return is_liked

    async def unlike(self, tweet_id: int) -> dict:
        response_json = await self._interact_with_tweet('UnfavoriteTweet', tweet_id)
        is_unliked = 'data' in response_json and response_json['data']['unfavorite_tweet'] == 'Done'
        return is_unliked

    async def delete_tweet(self, tweet_id: int | str) -> bool:
        """Delete a tweet by its id"""
        url, query_id = self._action_to_url('DeleteTweet')
        json_payload = {
            'variables': {
                'tweet_id': tweet_id,
                'dark_request': False,
            },
            'queryId': query_id,
        }
        response, response_json = await self.request("POST", url, json=json_payload)
        is_deleted = "data" in response_json and "delete_tweet" in response_json["data"]
        return is_deleted

    async def pin_tweet(self, tweet_id: str | int) -> bool:
        url = 'https://api.twitter.com/1.1/account/pin_tweet.json'
        data = {
            'tweet_mode': 'extended',
            'id': str(tweet_id),
        }
        headers = {
            'content-type': 'application/x-www-form-urlencoded',
        }
        response, response_json = await self.request("POST", url, headers=headers, data=data)
        is_pinned = bool(response_json["pinned_tweets"])
        return is_pinned

    async def _tweet(
            self,
            text: str = None,
            *,
            media_id: int | str = None,
            tweet_id_to_reply: str | int = None,
            attachment_url: str = None,
    ) -> int:
        """Returns tweet_id"""
        url, query_id = self._action_to_url('CreateTweet')
        payload = {
            'variables': {
                'tweet_text': text if text is not None else "",
                'dark_request': False,
                'media': {
                    'media_entities': [],
                    'possibly_sensitive': False},
                'semantic_annotation_ids': [],
            },
            'features': {
                'tweetypie_unmention_optimization_enabled': True,
                'responsive_web_edit_tweet_api_enabled': True,
                'graphql_is_translatable_rweb_tweet_is_translatable_enabled': True,
                'view_counts_everywhere_api_enabled': True,
                'longform_notetweets_consumption_enabled': True,
                'tweet_awards_web_tipping_enabled': False,
                'longform_notetweets_rich_text_read_enabled': True,
                'longform_notetweets_inline_media_enabled': True,
                'responsive_web_graphql_exclude_directive_enabled': True,
                'verified_phone_label_enabled': False,
                'freedom_of_speech_not_reach_fetch_enabled': True,
                'standardized_nudges_misinfo': True,
                'tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled': False,
                'responsive_web_graphql_skip_user_profile_image_extensions_enabled': False,
                'responsive_web_graphql_timeline_navigation_enabled': True,
                'responsive_web_enhance_cards_enabled': False,
                'responsive_web_twitter_article_tweet_consumption_enabled': False,
                'responsive_web_media_download_video_enabled': False
            },
            'queryId': query_id,
        }
        if attachment_url:
            payload['variables']['attachment_url'] = attachment_url
        if tweet_id_to_reply:
            payload['variables']['reply'] = {
                'in_reply_to_tweet_id': str(tweet_id_to_reply),
                'exclude_reply_user_ids': [],
            }
        if media_id:
            payload['variables']['media']['media_entities'].append({'media_id': str(media_id), 'tagged_users': []})

        response, response_json = await self.request("POST", url, json=payload)
        tweet_id = response_json['data']['create_tweet']['tweet_results']['result']['rest_id']
        return tweet_id

    async def tweet(self, text: str, *, media_id: int | str = None) -> int:
        return await self._tweet(text, media_id=media_id)

    async def reply(self, tweet_id: str | int, text: str, *, media_id: int | str = None) -> int:
        return await self._tweet(text, media_id=media_id, tweet_id_to_reply=tweet_id)

    async def quote(self, tweet_url: str, text: str, *, media_id: int | str = None) -> int:
        return await self._tweet(text, media_id=media_id, attachment_url=tweet_url)

    async def vote(self, tweet_id: int | str, card_id: int | str, choice_number: int) -> dict:
        url = "https://caps.twitter.com/v2/capi/passthrough/1"
        params = {
            "twitter:string:card_uri": f"card://{card_id}",
            "twitter:long:original_tweet_id": str(tweet_id),
            "twitter:string:response_card_name": "poll2choice_text_only",
            "twitter:string:cards_platform": "Web-12",
            "twitter:string:selected_choice": str(choice_number),
        }
        response, response_json = await self.request("POST", url, params=params)
        return response_json

    async def _request_users(self, action: str, user_id: int | str, count: int) -> list[UserData]:
        url, query_id = self._action_to_url(action)
        variables = {
            'userId': str(user_id),
            'count': count,
            'includePromotedContent': False,
        }
        features = {
            "rweb_lists_timeline_redesign_enabled": True,
            "responsive_web_graphql_exclude_directive_enabled": True,
            "verified_phone_label_enabled": False,
            "creator_subscriptions_tweet_preview_api_enabled": True,
            "responsive_web_graphql_timeline_navigation_enabled": True,
            "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
            "tweetypie_unmention_optimization_enabled": True,
            "responsive_web_edit_tweet_api_enabled": True,
            "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
            "view_counts_everywhere_api_enabled": True,
            "longform_notetweets_consumption_enabled": True,
            "responsive_web_twitter_article_tweet_consumption_enabled": False,
            "tweet_awards_web_tipping_enabled": False,
            "freedom_of_speech_not_reach_fetch_enabled": True,
            "standardized_nudges_misinfo": True,
            "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
            "longform_notetweets_rich_text_read_enabled": True,
            "longform_notetweets_inline_media_enabled": True,
            "responsive_web_media_download_video_enabled": False,
            "responsive_web_enhance_cards_enabled": False
        }
        params = {
            'variables': to_json(variables),
            'features': to_json(features),
        }
        response, response_json = await self.request("GET", url, params=params)

        users = []
        if 'result' in response_json['data']['user']:
            entries = response_json['data']['user']['result']['timeline']['timeline']['instructions'][-1]['entries']
            for entry in entries:
                if entry['entryId'].startswith('user'):
                    user_data_dict = entry["content"]["itemContent"]["user_results"]["result"]
                    users.append(UserData(user_data_dict))
        return users

    @staticmethod
    def ensure_user_id(func):
        @wraps(func)
        async def wrapper(self, user_id: int | str = None, *args, **kwargs):
            if user_id is None:
                if not self.account.data:
                    await self.request_user_data()
                user_id = self.account.data.id
            return await func(self, user_id, *args, **kwargs)
        return wrapper

    @ensure_user_id
    async def request_followers(self, user_id: int | str = None, count: int = 10) -> list[UserData]:
        return await self._request_users('Followers', user_id, count)

    @ensure_user_id
    async def request_followings(self, user_id: int | str = None, count: int = 10) -> list[UserData]:
        return await self._request_users('Following', user_id, count)

    async def _request_tweet_data(self, tweet_id: int) -> dict:
        action = 'TweetDetail'
        url, query_id = self._action_to_url(action)
        variables = {
            "focalTweetId": str(tweet_id),
            "with_rux_injections": False,
            "includePromotedContent": True,
            "withCommunity": True,
            "withQuickPromoteEligibilityTweetFields": True,
            "withBirdwatchNotes": True,
            "withVoice": True,
            "withV2Timeline": True,
        }
        features = {
            "rweb_lists_timeline_redesign_enabled": True,
            "responsive_web_graphql_exclude_directive_enabled": True,
            "verified_phone_label_enabled": False,
            "creator_subscriptions_tweet_preview_api_enabled": True,
            "responsive_web_graphql_timeline_navigation_enabled": True,
            "responsive_web_graphql_skip_user_profile_image_extensions_enabled": False,
            "tweetypie_unmention_optimization_enabled": True,
            "responsive_web_edit_tweet_api_enabled": True,
            "graphql_is_translatable_rweb_tweet_is_translatable_enabled": True,
            "view_counts_everywhere_api_enabled": True,
            "longform_notetweets_consumption_enabled": True,
            "tweet_awards_web_tipping_enabled": False,
            "freedom_of_speech_not_reach_fetch_enabled": True,
            "standardized_nudges_misinfo": True,
            "tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled": True,
            "longform_notetweets_rich_text_read_enabled": True,
            "longform_notetweets_inline_media_enabled": True,
            "responsive_web_enhance_cards_enabled": False,
        }
        params = {
            'variables': to_json(variables),
            'features': to_json(features),
        }
        response, response_json = await self.request("GET", url, params=params)
        return response_json

    async def _update_profile_image(self, type: str, media_id: str | int) -> bool:
        url = f"https://api.twitter.com/1.1/account/{type}.json"
        params = {
            'include_profile_interstitial_type': '1',
            'include_blocking': '1',
            'include_blocked_by': '1',
            'include_followed_by': '1',
            'include_want_retweets': '1',
            'include_mute_edge': '1',
            'include_can_dm': '1',
            'include_can_media_tag': '1',
            'include_ext_has_nft_avatar': '1',
            'include_ext_is_blue_verified': '1',
            'include_ext_verified_type': '1',
            'include_ext_profile_image_shape': '1',
            'skip_status': '1',
            'return_user': 'true',
            'media_id': str(media_id),
        }
        response, response_json = await self.request("POST", url, params=params)
        is_updated = "id" in response_json
        return is_updated

    async def update_profile_avatar(self, media_id: int | str) -> bool:
        return await self._update_profile_image('update_profile_image', media_id)

    async def update_profile_banner(self, media_id: int | str) -> bool:
        return await self._update_profile_image('update_profile_banner', media_id)

    async def update_profile(
            self,
            birthdate_day: int,
            birthdate_month: int,
            birthdate_year: int,
            birthdate_visibility: str = 'self',
            birthdate_year_visibility: str = 'self',
            name: str = None,
            description: str = None,
            location: str = None,
            website: str = None,
    ):
        url = "https://api.twitter.com/1.1/account/update_profile.json"
        params = {
            'birthdate_visibility': birthdate_visibility,
            'birthdate_year_visibility': birthdate_year_visibility,
        }
        if name: params['name'] = name
        if description: params['description'] = description
        if location: params['location'] = location
        if website: params['url'] = website
        if birthdate_day: params['birthdate_day'] = birthdate_day
        if birthdate_month: params['birthdate_month'] = birthdate_month
        if birthdate_year: params['birthdate_year'] = birthdate_year
        response, response_json = await self.request("POST", url, params=params)
        is_updated = "id" in response_json
        return is_updated
