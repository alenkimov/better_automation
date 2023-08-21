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
    queryId_like = 'lI07N6Otwv1PhnEgXILM7A'
    queryId_retweet = 'ojPdsZsimiJrUGLR1sjUtA'
    queryId_create_tweet = 'SoVnbfCycZ7fERGCwpZkYA'
    queryId_handler_converter = '9zwVLJ48lmVUk8u_Gh9DmA'
    queryId_tweet_parser = 'Uuw5X2n3tuGE_SatnXUqLA'
    queryId_tweet_details = 'VWFGPVAGkZMGRKGe3GFFnA'
    base_url = 'https://twitter.com/i/api/graphql'

    def __init__(self, session: aiohttp.ClientSession, auth_token: str, *args, **kwargs):
        super().__init__(session, *args, **kwargs)
        self.session.headers.update(self.DEFAULT_HEADERS)
        self._auth_token = None
        self._ct0 = None
        self.set_auth_token(auth_token)
        self.set_ct0("")

    def set_auth_token(self, auth_token: str):
        self._auth_token = auth_token
        self.session.cookie_jar.update_cookies({"auth_token": auth_token})

    def set_ct0(self, ct0: str):
        self._ct0 = ct0
        self.session.headers["x-csrf-token"] = ct0
        self.session.cookie_jar.update_cookies({"ct0": ct0})

    @property
    def auth_token(self) -> str | None:
        return self._auth_token

    @property
    def ct0(self) -> str | None:
        return self._ct0

    async def request(self, *args, **kwargs) -> aiohttp.ClientResponse:
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

        return response

    async def _request_ct0(self) -> str:
        url = 'https://twitter.com/i/api/2/oauth2/authorize'
        try:
            response = await self.request("GET", url)
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
    async def _confirm_binding(self, bind_code: str):
        data = {
            'approval': 'true',
            'code': bind_code,
        }
        headers = {'content-type': 'application/x-www-form-urlencoded'}
        await self.request("POST", 'https://twitter.com/i/api/2/oauth2/authorize', headers=headers, data=data)

    async def bind_app(self, *args, **kwargs):
        bind_code = await self._request_bind_code(*args, **kwargs)
        await self._confirm_binding(bind_code)
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
        response = await self.request("GET", url, params=params)
        response_data: dict = await response.json()
        username = response_data.get("screen_name")
        return username

    @ensure_ct0
    async def request_user_id(self, user_handle: str):
        if user_handle.startswith("@"):
            user_handle = user_handle[1:]

        url = f"{self.base_url}/{self.queryId_handler_converter}/ProfileSpotlightsQuery"

        params = {
            'variables': to_json({"screen_name": f"{user_handle}"}),
        }
        response = await self.request("GET", url, params=params)
        response_json = await response.json()
        user_id = str(response_json['data']['user_result_by_screen_name']['result']['rest_id'])
        return user_id

    @ensure_ct0
    async def follow(self, user_id: str) -> bool:
        url = "https://twitter.com/i/api/1.1/friendships/create.json"
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
        response = await self.request("POST", url, params=params)
        response_json = await response.json()
        return "id" in response_json

    @ensure_ct0
    async def like(self, tweet_id: str | int) -> bool:
        url = f"{self.base_url}/{self.queryId_like}/FavoriteTweet"
        json_data = {
            'variables': {
                'tweet_id': str(tweet_id),
            },
            'queryId': self.queryId_like,
        }
        response = await self.request("POST", url, json=json_data)
        response_json = await response.json()
        return "data" in response_json and response_json['data']['favorite_tweet'] == 'Done'

    @staticmethod
    async def _handle_media_request(response: aiohttp.ClientResponse):
        content = await response.read()
        encoding = response.charset or 'utf-8'
        decoded_content = content.decode(encoding, errors='ignore')
        return decoded_content

    @ensure_ct0
    async def upload_image(self, image_url: str) -> int:
        async def request_image(url: str) -> aiohttp.ClientResponse:
            return await super(TwitterAPI, self).request("GET", url)

        async def _init(total_bytes):
            params = {
                'command': 'INIT',
                'total_bytes': total_bytes,
                'media_type': 'image/jpeg',
                'media_category': 'tweet_image',
            }
            response = await self.request("POST", 'https://upload.twitter.com/i/media/upload.json', params=params)
            response_data = await response.json()
            return response_data['media_id_string']

        async def _append(media_id, image_as_bytes: bytes):
            params = {
                'command': 'APPEND',
                'media_id': str(media_id),
                'segment_index': '0',
            }
            await self.request("OPTIONS", 'https://upload.twitter.com/i/media/upload.json', params=params)

            writer = MultipartWriter(boundary='----WebKitFormBoundaryCGqmEUMuU9BgPiZm')
            part = writer.append(image_as_bytes)
            part.set_content_disposition('form-data', name="media", filename="blob")
            part.headers['Content-Type'] = 'application/octet-stream'
            headers = {'content-type': writer.headers['Content-Type']}
            await self.request("POST", 'https://upload.twitter.com/i/media/upload.json',
                               headers=headers,  params=params, data=writer)

        async def _finalize(media_id):
            params = {
                'command': 'FINALIZE',
                'media_id': str(media_id),
            }
            await self.request("POST", 'https://upload.twitter.com/i/media/upload.json', params=params)

        image_response = await request_image(image_url)
        media_id = await _init(image_response.content.total_bytes)
        await _append(media_id, await image_response.read())
        await _finalize(media_id)
        return media_id

    async def _create_tweet(self, json: dict) -> int:
        """
        :return: Tweet ID
        """
        response = await self.request("POST", f"{self.base_url}/{self.queryId_create_tweet}/CreateTweet", json=json)
        response_json = await response.json()
        tweet_id = response_json['data']['create_tweet']['tweet_results']['result']['rest_id']
        return int(tweet_id)

    async def _create_retweet(self, json: dict) -> int:
        """
        :return: Retweet ID
        """
        response = await self.request("POST", f"{self.base_url}/{self.queryId_retweet}/CreateRetweet", json=json)
        response_json = await response.json()
        retweet_id = response_json['data']['create_retweet']['retweet_results']['result']['rest_id']
        return int(retweet_id)

    @ensure_ct0
    async def tweet(
            self,
            text: str = None,
            *,
            media_id: int = None,
            tweet_id_for_reply: str | int = None,
    ) -> int:
        """
        :return: Tweet ID
        """
        if text is None:
            text = ""

        json_data = {
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
            'queryId': self.queryId_create_tweet,
        }
        if tweet_id_for_reply:
            json_data['variables']['reply'] = {
                'in_reply_to_tweet_id': str(tweet_id_for_reply),
                'exclude_reply_user_ids': [],
            }
        if media_id:
            json_data['variables']['media'] = {
                'media_entities': [
                    {
                        'media_id': media_id,
                        'tagged_users': [],
                    },
                ],
                'possibly_sensitive': False,
            }
        return await self._create_tweet(json_data)

    @ensure_ct0
    async def reply(self, tweet_id: int, text: str) -> int:
        """
        :return: Tweet ID
        """
        json_data = {
            'variables': {
                'tweet_text': text,
                'reply': {
                    'in_reply_to_tweet_id': str(tweet_id),
                    'exclude_reply_user_ids': [],
                },
                'dark_request': False,
                'media': {
                    'media_entities': [],
                    'possibly_sensitive': False,
                },
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
                'tweet_with_visibility_results_prefer_gql_limited_actions_policy_enabled': True,
                'responsive_web_graphql_skip_user_profile_image_extensions_enabled': False,
                'responsive_web_graphql_timeline_navigation_enabled': True,
                'responsive_web_enhance_cards_enabled': False,
                'responsive_web_media_download_video_enabled': False,
                'responsive_web_twitter_article_tweet_consumption_enabled': False
            },
            'queryId': self.queryId_create_tweet,
        }
        return await self._create_tweet(json_data)

    @ensure_ct0
    async def retweet(self, tweet_id: int) -> int:
        """
        :return: Retweet ID
        """
        json_data = {
            'variables': {
                'tweet_id': str(tweet_id),
            },
            'queryId': self.queryId_retweet,
        }
        return await self._create_retweet(json_data)

    @ensure_ct0
    async def pin_tweet(self, tweet_id: int) -> bool:
        """
        :return: True if pinned
        """
        data = {
            'tweet_mode': 'extended',
            'id': str(tweet_id),
        }
        headers = {
            'content-type': 'application/x-www-form-urlencoded',
        }
        response = await self.request("POST", 'https://api.twitter.com/1.1/account/pin_tweet.json', headers=headers, data=data)
        response_json = await response.json()
        return 'pinned_tweets' in response_json

    @ensure_ct0
    async def request_tweet_data(self, tweet_id: int) -> list[dict]:
        tweet_details = []

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
        url = f"{self.base_url}/{self.queryId_tweet_details}/TweetDetail"
        response = await self.request("GET", url, params=params)
        response_json = await response.json()

        if response_json.get('data'):
            tweet_data = response_json['data']['threaded_conversation_with_injections_v2']['instructions'][0]['entries']
            tweet_owner_id = tweet_data[0]['content']['itemContent']['tweet_results']['result']['legacy'][
                'user_id_str']
            try:
                tweet = tweet_data[1]
                entryId = tweet['entryId']
                in_reply_to_user_id_str = tweet['content']['items'][0]['item'].get('itemContent').get(
                    'tweet_results').get(
                    'result').get('legacy').get('in_reply_to_user_id_str')
                in_reply_to_status_id_str = tweet['content']['items'][0]['item'].get('itemContent').get(
                    'tweet_results').get('result').get('legacy').get('in_reply_to_status_id_str')
                if entryId.find('conversationthread') != -1 and (
                        in_reply_to_status_id_str and in_reply_to_user_id_str) and int(
                    in_reply_to_status_id_str) == int(tweet_id) and int(in_reply_to_user_id_str) == int(
                    tweet_owner_id):
                    tweet_items = tweet['content']['items']
                    for item in tweet_items:
                        try:
                            in_reply_to_status_id_str = item['item']['itemContent']['tweet_results']['result'][
                                'legacy'].get('in_reply_to_status_id_str')
                            user_id = item['item']['itemContent']['tweet_results']['result']['legacy'][
                                'user_id_str']

                            if int(tweet_owner_id) == int(user_id) and int(in_reply_to_status_id_str) == int(
                                    tweet_id):
                                tweet_id = item['item']['itemContent']['tweet_results']['result'].get('rest_id')
                                text = item['item']['itemContent']['tweet_results']['result']['legacy']['full_text']
                                if item.get('item').get('itemContent').get('tweet_results').get('result').get(
                                        'legacy').get('extended_entities'):
                                    media_url = item['item']['itemContent']['tweet_results']['result']['legacy'][
                                        'extended_entities']['media'][0]['media_url_https']
                                else:
                                    media_url = None
                                tweet_details.append({'text': text, 'media_url': media_url})
                        except KeyError:
                            pass
            except IndexError:
                pass
        return tweet_details
