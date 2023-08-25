from functools import wraps

import aiohttp
from aiohttp import MultipartWriter
from aiohttp.client_exceptions import ContentTypeError

from .errors import (
    TwitterAPIException,
    HTTPException,
    BadRequest,
    Unauthorized,
    Forbidden,
    NotFound,
    TooManyRequests,
    TwitterServerError,
)
from ..http import BetterHTTPClient
from ..utils import to_json


class TwitterAPI(BetterHTTPClient):
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
    GRAPHQL_URL = 'https://twitter.com/i/api/graphql'
    ACTION_TO_QUERY_ID = {
        'CreateRetweet': "ojPdsZsimiJrUGLR1sjUtA",
        'FavoriteTweet': "lI07N6Otwv1PhnEgXILM7A",
        'UnfavoriteTweet': "ZYKSe-w7KEslx3JhSIk5LA",
        # 'CreateTweet': "GUFG748vuvmewdXbB5uPKg",  # OLD
        'CreateTweet': "SoVnbfCycZ7fERGCwpZkYA",
        'TweetResultByRestId': "V3vfsYzNEyD9tsf4xoFRgw",
        'ModerateTweet': "p'jF:GVqCjTcZol0xcBJjw",
        'DeleteTweet': "VaenaVgh5q5ih7kvyVjgtg",
        'UserTweets': "Uuw5X2n3tuGE_SatnXUqLA",
        'TweetDetail': 'VWFGPVAGkZMGRKGe3GFFnA',
        'ProfileSpotlightsQuery': '9zwVLJ48lmVUk8u_Gh9DmA',
        'Following': 't-BPOrMIduGUJWO_LxcvNQ',
        'Followers': '3yX7xr2hKjcZYnXt6cU6lQ',
    }

    def __init__(self, session: aiohttp.ClientSession, auth_token: str, ct0: str = None, *args, **kwargs):
        super().__init__(session, *args, **kwargs)
        self._headers.update(self.DEFAULT_HEADERS)
        self._auth_token = None
        self._ct0 = None
        self.set_auth_token(auth_token)
        self.set_ct0(ct0 if ct0 else '')

    def set_auth_token(self, auth_token: str):
        self._auth_token = auth_token
        self._cookies.update({"auth_token": auth_token})

    def set_ct0(self, ct0: str):
        self._ct0 = ct0
        self._cookies.update({"ct0": ct0})
        self._headers.update({"x-csrf-token": ct0})

    @property
    def auth_token(self) -> str | None:
        return self._auth_token

    @property
    def ct0(self) -> str | None:
        return self._ct0

    async def request(self, *args, **kwargs) -> tuple[aiohttp.ClientResponse, dict | None]:
        response = await super().request(*args, **kwargs)

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

        if response_json and "errors" in response_json:
            raise HTTPException(response, response_json)

        return response, response_json

    @classmethod
    def _action_to_url(cls, action: str) -> tuple[str, str]:
        """Returns url and query_id"""
        query_id = cls.ACTION_TO_QUERY_ID[action]
        return f"{cls.GRAPHQL_URL}/{query_id}/{action}", query_id

    async def _request_ct0(self) -> str:
        url = 'https://twitter.com/i/api/2/oauth2/authorize'
        try:
            response, _ = await self.request("GET", url)
            if "ct0" in response.cookies:
                return response.cookies["ct0"].value
            else:
                raise TwitterAPIException("Failed to obtain ct0")
        except Forbidden as e:
            if "ct0" in e.response.cookies:
                return e.response.cookies["ct0"].value
            else:
                raise

    @staticmethod
    def _ensure_ct0(coro):
        @wraps(coro)
        async def wrapper(self, *args, **kwargs):
            if not self.ct0:
                self.set_ct0(await self._request_ct0())
            return await coro(self, *args, **kwargs)

        return wrapper

    @_ensure_ct0
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
        response, data = await self.request("GET", url, params=querystring)
        code = data["auth_code"]
        return code

    @_ensure_ct0
    async def _confirm_binding(self, bind_code: str):
        data = {
            'approval': 'true',
            'code': bind_code,
        }
        headers = {'content-type': 'application/x-www-form-urlencoded'}
        await self.request("POST", 'https://twitter.com/i/api/2/oauth2/authorize', headers=headers, data=data)

    @_ensure_ct0
    async def _request_user_id(self, screen_name: str) -> dict:
        url, query_id = self._action_to_url('ProfileSpotlightsQuery')
        params = {'variables': to_json({"screen_name": screen_name})}
        response, data = await self.request("GET", url, params=params)
        return data

    @_ensure_ct0
    async def _upload_image_init(self, total_bytes) -> dict:
        params = {
            'command': 'INIT',
            'total_bytes': total_bytes,
            'media_type': 'image/jpeg',
            'media_category': 'tweet_image',
        }
        response, data = await self.request("POST", 'https://upload.twitter.com/i/media/upload.json', params=params)
        return data

    @_ensure_ct0
    async def _upload_image_append(self, media_id, image_as_bytes: bytes):
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

    @_ensure_ct0
    async def _upload_image_finalize(self, media_id):
        url = 'https://upload.twitter.com/i/media/upload.json'
        params = {
            'command': 'FINALIZE',
            'media_id': str(media_id),
        }
        await self.request("POST", url, params=params)

    async def _upload_image(self, image: bytes) -> dict:
        media_data = await self._upload_image_init(len(image))
        media_id = media_data['media_id_string']
        await self._upload_image_append(media_id, image)
        await self._upload_image_finalize(media_id)
        return media_data

    @_ensure_ct0
    async def _follow_action(self, action: str, user_id: int | str):
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
            'content-type': 'application/x-www-form-urlencoded'
        }
        response, data = await self.request("POST", url, params=params, headers=headers)
        # response, data = await self.request("POST", url, params=params)
        return data

    async def _follow(self, user_id: str | int) -> dict:
        return await self._follow_action("create", user_id)

    async def _unfollow(self, user_id: str | int) -> dict:
        return await self._follow_action("destroy", user_id)

    @_ensure_ct0
    async def _interact_with_tweet(self, action: str, tweet_id: int) -> dict:
        url, query_id = self._action_to_url(action)
        json_payload = {
            'variables': {
                'tweet_id': tweet_id,
                'dark_request': False
            },
            'queryId': query_id
        }
        response, data = await self.request("POST", url, json=json_payload)
        return data

    async def _repost(self, tweet_id: int) -> dict:
        return await self._interact_with_tweet('CreateRetweet', tweet_id)

    async def _like(self, tweet_id: int) -> dict:
        return await self._interact_with_tweet('FavoriteTweet', tweet_id)

    async def _unlike(self, tweet_id: int) -> dict:
        return await self._interact_with_tweet('UnfavoriteTweet', tweet_id)

    @_ensure_ct0
    async def _delete_tweet(self, tweet_id: int | str) -> dict:
        url, query_id = self._action_to_url('DeleteTweet')
        json_payload = {
            'variables': {
                'tweet_id': tweet_id,
                'dark_request': False,
            },
            'queryId': query_id,
        }
        response, data = await self.request("POST", url, json=json_payload)
        return data

    @_ensure_ct0
    async def _pin_tweet(self, tweet_id: str | int) -> dict:
        url = 'https://api.twitter.com/1.1/account/pin_tweet.json'
        data = {
            'tweet_mode': 'extended',
            'id': str(tweet_id),
        }
        headers = {
            'content-type': 'application/x-www-form-urlencoded',
        }
        response, data = await self.request("POST", url, headers=headers, data=data)
        return data

    @_ensure_ct0
    async def _tweet(
            self,
            text: str = None,
            *,
            media_id: int | str = None,
            tweet_id_to_reply: str | int = None,
            attachment_url: str = None,
    ) -> dict:
        if text is None:
            text = ""

        action = 'CreateTweet'
        url, query_id = self._action_to_url(action)

        payload = {
            'variables': {
                'tweet_text': text,
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

        response, data = await self.request("POST", url, json=payload)
        return data

    @_ensure_ct0
    async def _request_users(self, action: str, user_id: int | str, count: int) -> dict:
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
        response, data = await self.request("GET", url, params=params)
        return data

    async def _request_followers(self, user_id: int | str, count: int) -> dict:
        return await self._request_users('Followers', user_id, count)

    async def _request_following(self, user_id: int | str, count: int) -> dict:
        return await self._request_users('Following', user_id, count)

    @_ensure_ct0
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
        response, data = await self.request("GET", url, params=params)
        return data

    @_ensure_ct0
    async def _request_username(self) -> dict:
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
        response, data = await self.request("GET", url, params=params)
        return data

    @_ensure_ct0
    async def _update_profile_image(self, type: str, media_id: str | int) -> dict:
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
        response, data = await self.request("POST", url, params=params)
        return data

    async def _update_profile_avatar(self, media_id: int | str) -> dict:
        return await self._update_profile_image('update_profile_image', media_id)

    async def _update_profile_banner(self, media_id: int | str) -> dict:
        return await self._update_profile_image('update_profile_banner', media_id)

    @_ensure_ct0
    async def _update_profile(
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
        response, data = await self.request("POST", url, params=params)
        return data

    # @_ensure_ct0
    # async def _update_username(self, username: str) -> dict:
    #     url = 'https://twitter.com/i/api/1.1/account/settings.json'
    #     payload = {
    #         'include_mention_filter': True,
    #         'include_nsfw_user_flag': True,
    #         'include_nsfw_admin_flag': True,
    #         'include_ranked_timeline': True,
    #         'include_alt_text_compose': True,
    #         'screen_name': username,
    #     }
    #     headers = {
    #         'content-type': 'application/x-www-form-urlencoded'
    #     }
    #     response, data = await self.request("POST", url, headers=headers, json=payload)
    #     return data

    async def bind_app(
            self,
            client_id: str,
            code_challenge: str,
            state: str,
            redirect_uri: str,
            code_challenge_method: str = "plain",
            scope: str = "tweet.read users.read follows.read offline.access like.read",
            response_type: str = "code",
    ):
        bind_code = await self._request_bind_code(
            client_id, code_challenge, state, redirect_uri, code_challenge_method, scope, response_type,
        )
        await self._confirm_binding(bind_code)
        return bind_code

    async def upload_image(self, image_url: str) -> str:
        """Upload image by image URL. Returns media_id"""
        image_response = await super(TwitterAPI, self).request("GET", image_url)
        data = await self._upload_image(await image_response.read())
        media_id = data['media_id_string']
        return media_id

    async def request_user_id(self, username: str) -> int:
        if username.startswith("@"):
            username = username[1:]
        data = await self._request_user_id(username)
        user_id = data['data']['user_result_by_screen_name']['result']['rest_id']
        return int(user_id)

    async def follow(self, user_id: str | int) -> bool:
        data = await self._follow(user_id)
        return "id" in data

    async def unfollow(self, user_id: str | int) -> bool:
        data = await self._unfollow(user_id)
        return "id" in data

    async def like(self, tweet_id: str | int) -> bool:
        data = await self._like(tweet_id)
        return data['data']['favorite_tweet'] == 'Done'

    async def unlike(self, tweet_id: str | int) -> bool:
        data = await self._unlike(tweet_id)
        return "data" in data and data['data']['unfavorite_tweet'] == 'Done'

    async def _tweet_and_return_tweet_id(self, *args, **kwargs) -> int:
        data = await self._tweet(*args, **kwargs)
        tweet_id = data['data']['create_tweet']['tweet_results']['result']['rest_id']
        return tweet_id

    async def tweet(self, text: str, *, media_id: int | str = None) -> int:
        return await self._tweet_and_return_tweet_id(text, media_id=media_id)

    async def reply(self, tweet_id: str | int, text: str, *, media_id: int | str = None) -> int:
        return await self._tweet_and_return_tweet_id(text, media_id=media_id, tweet_id_to_reply=tweet_id)

    async def quote(self, tweet_url: str, text: str, *, media_id: int | str = None) -> int:
        return await self._tweet_and_return_tweet_id(text, media_id=media_id, attachment_url=tweet_url)

    async def repost(self, tweet_id: str | int) -> int:
        """Repost (retweet) a tweet by its id"""
        data = await self._repost(tweet_id)
        retweet_id = data['data']['create_retweet']['retweet_results']['result']['rest_id']
        return int(retweet_id)

    async def delete_tweet(self, tweet_id: int) -> bool:
        """Delete a tweet by its id"""
        data = await self._delete_tweet(tweet_id)
        return "data" in data and "delete_tweet" in data["data"]

    async def pin_tweet(self, tweet_id: str | int) -> bool:
        data = await self._pin_tweet(tweet_id)
        return 'pinned_tweets' in data

    async def request_followers(self, user_id: int | str, count: int = 10) -> dict[int: str]:
        data = await self._request_followers(user_id, count)
        users = {}
        if 'result' in data['data']['user']:
            entries = data['data']['user']['result']['timeline']['timeline']['instructions'][-1]['entries']
            for entry in entries:
                if entry['entryId'].startswith('user'):
                    user_id = int(entry['entryId'][6:])
                    username = entry["content"]["itemContent"]["user_results"]["result"]["legacy"]["screen_name"]
                    users[user_id] = username
        return users

    async def request_followings(self, user_id: int | str, count: int = 10) -> dict[int: str]:
        data = await self._request_following(user_id, count)
        users = {}
        if 'result' in data['data']['user']:
            entries = data['data']['user']['result']['timeline']['timeline']['instructions'][-1]['entries']

            for entry in entries:
                if entry['entryId'].startswith('user'):
                    user_id = int(entry['entryId'][6:])
                    username = entry["content"]["itemContent"]["user_results"]["result"]["legacy"]["screen_name"]
                    users[user_id] = username
        return users

    async def request_username(self):
        data = await self._request_username()
        return data['screen_name']

    async def update_profile(self, *args, **kwargs) -> bool:
        data = await self._update_profile(*args, **kwargs)
        return 'id' in data

    async def update_profile_avatar(self, media_id: int | str) -> bool:
        data = await self._update_profile_avatar(media_id)
        return "id" in data

    async def update_profile_banner(self, media_id: int | str) -> bool:
        data = await self._update_profile_banner(media_id)
        return "id" in data

    # async def update_username(self, username: str) -> bool:
    #     if username.startswith("@"):
    #         username = username[1:]
    #     data = await self._update_username(username)
    #     return data
