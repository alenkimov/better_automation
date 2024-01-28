from datetime import datetime

from bs4 import BeautifulSoup


def parse_oauth_html(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    result = {
        "oauth_token": soup.find("input", attrs={"name": "authenticity_token"}).get("value"),
        "authenticity_token": soup.find("input", attrs={"name": "authenticity_token"}).get("value"),
    }
    redirect_url_element = soup.find("a", text="click here to continue")
    if redirect_url_element: result["redirect_url"] = redirect_url_element.get("href")
    redirect_after_login_element = soup.find("input", attrs={"name": "redirect_after_login"})
    if redirect_after_login_element: result["redirect_after_login_url"] = redirect_after_login_element.get("value")
    return result


def remove_at_sign(username: str) -> str:
    if username.startswith("@"):
        return username[1:]
    return username


def tweet_url(username: str, tweet_id: int) -> str:
    """
    :return: Tweet URL
    """
    return f"https://x.com/{username}/status/{tweet_id}"


def to_datetime(twitter_datetime: str):
    return datetime.strptime(twitter_datetime, '%a %b %d %H:%M:%S +0000 %Y')
