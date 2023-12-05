import asyncio
import base64
import time
from typing import Any, Literal
from time import time

from curl_cffi import requests
from yarl import URL

from better_automation.twitter.errors import (
    HTTPException,
    BadRequest,
    Unauthorized,
    Forbidden,
    NotFound,
    RateLimited,
    TwitterServerError,
)
from ..utils import to_json
from ..base import BaseClient
from .account import TwitterAccount, TwitterAccountStatus
from .models import TwitterUserData


def remove_at_sign(username: str) -> str:
    if username.startswith("@"):
        return username[1:]
    return username


class TwitterClient(BaseClient):
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
        """
        :return: URL and Query ID
        """
        query_id = cls.ACTION_TO_QUERY_ID[action]
        url = f"{cls.GRAPHQL_URL}/{query_id}/{action}"
        return url, query_id

    def __init__(
            self,
            account: TwitterAccount,
            *,
            wait_on_rate_limit: bool = True,
            **session_kwargs,
    ):
        super().__init__(**session_kwargs)
        self.account = account
        self.wait_on_rate_limit = wait_on_rate_limit

    async def request(
            self,
            method,
            url,
            params: dict = None,
            headers: dict = None,
            json: Any = None,
            data: Any = None,
    ) -> tuple[requests.Response, Any]:
        cookies = {"auth_token": self.account.auth_token}
        headers = headers or {}

        if self.account.ct0:
            cookies["ct0"] = self.account.ct0
            headers["x-csrf-token"] = self.account.ct0

        response = await self.session.request(
                method, url,
                params=params,
                json=json,
                headers=headers,
                cookies=cookies,
                data=data,
        )
        response_json = response.json()

        if response.status_code == 400:
            raise BadRequest(response, response_json)

        if response.status_code == 401:
            exc = Unauthorized(response, response_json)

            if 32 in exc.api_codes:
                self.account.status = TwitterAccountStatus.BAD_TOKEN

            raise exc

        if response.status_code == 403:
            exc = Forbidden(response, response_json)

            if 353 in exc.api_codes and "ct0" in response.cookies:
                self.account.ct0 = response.cookies["ct0"]
                return await self.request(
                    method, url, params, headers, json, data,
                )

            if 64 in exc.api_codes:
                self.account.status = TwitterAccountStatus.SUSPENDED

            if 326 in exc.api_codes:
                self.account.status = TwitterAccountStatus.LOCKED

            raise exc

        if response.status_code == 404:
            raise NotFound(response, response_json)

        if response.status_code == 429:
            if self.wait_on_rate_limit:
                reset_time = int(response.headers["x-rate-limit-reset"])
                sleep_time = reset_time - int(time.time()) + 1
                if sleep_time > 0:
                    await asyncio.sleep(sleep_time)
                return await self.request(
                    method, url, params, headers, json, data,
                )
            else:
                raise RateLimited(response, response_json)

        if response.status_code >= 500:
            raise TwitterServerError(response, response_json)

        if not 200 <= response.status_code < 300:
            raise HTTPException(response, response_json)

        if "errors" in response_json:
            exc = HTTPException(response, response_json)

            if 141 in exc.api_codes:
                self.account.status = TwitterAccountStatus.SUSPENDED

            if 326 in exc.api_codes:
                self.account.status = TwitterAccountStatus.LOCKED

            raise exc

        self.account.status = TwitterAccountStatus.GOOD
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
    ) -> str:
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
        Запрашивает код авторизации для OAuth 2.0 авторизации.

        Привязка (бинд, линк) приложения.

        :param client_id: Идентификатор клиента, используемый для OAuth.
        :param code_challenge: Код-вызов, используемый для PKCE (Proof Key for Code Exchange).
        :param state: Уникальная строка состояния для предотвращения CSRF-атак.
        :param redirect_uri: URI перенаправления, на который будет отправлен ответ.
        :param code_challenge_method: Метод, используемый для преобразования code_verifier в code_challenge.
        :param scope: Строка областей доступа, запрашиваемых у пользователя.
        :param response_type: Тип ответа, который ожидается от сервера авторизации.
        :return: Код авторизации (привязки).
        """
        bind_code = await self._request_bind_code(
            client_id, code_challenge, state, redirect_uri, code_challenge_method, scope, response_type,
        )
        await self._confirm_binding(bind_code)
        return bind_code

    async def request_username(self):
        url = "https://twitter.com/i/api/1.1/account/settings.json"
        response, response_json = await self.request("POST", url)
        self.account.username = response_json["screen_name"]

    async def _request_user_data(self, username: str) -> TwitterUserData:
        url, query_id = self._action_to_url("UserByScreenName")
        username = remove_at_sign(username)
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
        user_data = TwitterUserData.from_raw_user_data(response_json["data"]["user"]["result"])

        if self.account.username == user_data.username:
            self.account.id = user_data.id
            self.account.name = user_data.name

        return user_data

    async def request_user_data(self, username: str = None) -> TwitterUserData:
        if username:
            return await self._request_user_data(username)
        else:
            if not self.account.username:
                await self.request_username()
            return await self._request_user_data(self.account.username)

    async def upload_image(self, image: bytes) -> int:
        """
        Upload image as bytes.

        :return: Media ID
        """
        url = "https://upload.twitter.com/1.1/media/upload.json"

        data = {"media_data": base64.b64encode(image)}
        response, response_json = await self.request("POST", url, data=data)
        media_id = response_json["media_id"]
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
        return bool(response_json)

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
        """
        Repost (retweet)

        :return: Tweet ID
        """
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
        """
        :return: Tweet ID
        """
        return await self._tweet(text, media_id=media_id)

    async def reply(self, tweet_id: str | int, text: str, *, media_id: int | str = None) -> int:
        """
        :return: Tweet ID
        """
        return await self._tweet(text, media_id=media_id, tweet_id_to_reply=tweet_id)

    async def quote(self, tweet_url: str, text: str, *, media_id: int | str = None) -> int:
        """
        :return: Tweet ID
        """
        return await self._tweet(text, media_id=media_id, attachment_url=tweet_url)

    async def vote(self, tweet_id: int | str, card_id: int | str, choice_number: int) -> dict:
        """
        :return: Raw vote information
        """
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

    async def _request_users(self, action: str, user_id: int | str, count: int) -> list[TwitterUserData]:
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
                    users.append(TwitterUserData.from_raw_user_data(user_data_dict))
        return users

    async def request_followers(self, user_id: int | str = None, count: int = 10) -> list[TwitterUserData]:
        """
        :param user_id: Текущий пользователь, если не передан ID иного пользователя.
        :param count: Количество подписчиков.
        """
        if user_id:
            return await self._request_users('Followers', user_id, count)
        else:
            if not self.account.id:
                await self.request_user_data()
            return await self._request_users('Followers', self.account.id, count)

    async def request_followings(self, user_id: int | str = None, count: int = 10) -> list[TwitterUserData]:
        """
        :param user_id: Текущий пользователь, если не передан ID иного пользователя.
        :param count: Количество подписчиков.
        """
        if user_id:
            return await self._request_users('Following', user_id, count)
        else:
            if not self.account.id:
                await self.request_user_data()
            return await self._request_users('Following', self.account.id, count)

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

    async def _update_profile_image(self, type: Literal["banner", "image"], media_id: str | int) -> str:
        """
        :return: Image URL
        """
        url = f"https://api.twitter.com/1.1/account/update_profile_{type}.json"
        params = {
            'media_id': str(media_id),
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
        }
        response, response_json = await self.request("POST", url, params=params)
        image_url = response_json[f"profile_{type}_url"]
        return image_url

    async def update_profile_avatar(self, media_id: int | str) -> str:
        """
        :return: Image URL
        """
        return await self._update_profile_image("image", media_id)

    async def update_profile_banner(self, media_id: int | str) -> str:
        """
        :return: Image URL
        """
        return await self._update_profile_image("banner", media_id)

    async def change_username(self, username: str) -> bool:
        url = "https://twitter.com/i/api/1.1/account/settings.json"
        data = {"screen_name": username}
        response, response_json = await self.request("POST", url, data=data)
        new_username = response_json["screen_name"]
        is_changed = new_username == username
        self.account.username = new_username
        return is_changed

    async def change_password(self, password: str) -> bool:
        """
        После изменения пароля обновляется auth_token!
        """
        if not self.account.password:
            raise ValueError(f"Specify the current password before changing it")

        url = "https://twitter.com/i/api/i/account/change_password.json"
        data = {
            "current_password": self.account.password,
            "password": password,
            "password_confirmation": password
        }
        response, response_json = await self.request("POST", url, data=data)
        is_changed = response_json["status"] == "ok"
        auth_token = response.cookies.get("auth_token", domain=".twitter.com")
        self.account.auth_token = auth_token
        self.account.password = password
        return is_changed

    async def update_profile(
            self,
            name: str = None,
            description: str = None,
            location: str = None,
            website: str = None,
    ) -> bool:
        """
        Locks an account!
        """
        if name is None and description is None:
            raise ValueError("Specify at least one param")

        url = "https://twitter.com/i/api/1.1/account/update_profile.json"
        headers = {"content-type": "application/x-www-form-urlencoded"}
        # Создаем словарь data, включая в него только те ключи, для которых значения не равны None
        data = {k: v for k, v in [
            ("name", name),
            ("description", description),
            ("location", location),
            ("url", website),
        ] if v is not None}
        response, response_json = await self.request("POST", url, headers=headers, data=data)
        # Проверяем, что все переданные параметры соответствуют полученным
        is_updated = all(response_json.get(key) == value for key, value in data.items() if key != "url")
        if website: is_updated &= URL(website) == URL(response_json["entities"]["url"]["urls"][0]["expanded_url"])
        return is_updated

    async def update_birthdate(
            self,
            day: int,
            month: int,
            year: int,
            visibility: Literal["self", "mutualfollow"] = "self",
            year_visibility: Literal["self"] = "self",
    ) -> bool:
        url = "https://twitter.com/i/api/1.1/account/update_profile.json"
        headers = {"content-type": "application/x-www-form-urlencoded"}
        data = {
            "birthdate_day": day,
            "birthdate_month": month,
            "birthdate_year": year,
            "birthdate_visibility": visibility,
            "birthdate_year_visibility": year_visibility,
        }
        response, response_json = await self.request("POST", url, headers=headers, data=data)
        birthdate_data = response_json["extended_profile"]["birthdate"]
        is_updated = all((
            birthdate_data["day"] == day,
            birthdate_data["month"] == month,
            birthdate_data["year"] == year,
            birthdate_data["visibility"] == visibility,
            birthdate_data["year_visibility"] == year_visibility,
        ))
        return is_updated

    async def send_message(self, user_id: int | str, text: str) -> dict:
        """
        :return: Event data
        """
        url = "https://api.twitter.com/1.1/direct_messages/events/new.json"
        payload = {"event": {
            "type": "message_create",
            "message_create": {
                "target": {
                    "recipient_id": user_id
                }, "message_data": {
                    "text": text}
            }
        }}
        response, response_json = await self.request("POST", url, json=payload)
        event_data = response_json["event"]
        return event_data

    async def request_messages(self) -> list[dict]:
        """
        :return: Messages data
        """
        url = 'https://twitter.com/i/api/1.1/dm/inbox_initial_state.json'
        params = {
            'nsfw_filtering_enabled': 'false',
            'filter_low_quality': 'false',
            'include_quality': 'all',
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
            'dm_secret_conversations_enabled': 'false',
            'krs_registration_enabled': 'true',
            'cards_platform': 'Web-12',
            'include_cards': '1',
            'include_ext_alt_text': 'true',
            'include_ext_limited_action_results': 'true',
            'include_quote_count': 'true',
            'include_reply_count': '1',
            'tweet_mode': 'extended',
            'include_ext_views': 'true',
            'dm_users': 'true',
            'include_groups': 'true',
            'include_inbox_timelines': 'true',
            'include_ext_media_color': 'true',
            'supports_reactions': 'true',
            'include_ext_edit_control': 'true',
            'include_ext_business_affiliations_label': 'true',
            'ext': 'mediaColor,altText,mediaStats,highlightedLabel,hasNftAvatar,voiceInfo,birdwatchPivot,superFollowMetadata,unmentionInfo,editControl',
        }
        response, response_json = await self.request("GET", url, params=params)
        messages = [entry["message"] for entry in response_json["inbox_initial_state"]["entries"] if "message" in entry]
        return messages
