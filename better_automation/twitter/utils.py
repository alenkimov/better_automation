from bs4 import BeautifulSoup


def parse_oauth_html(html: str) -> tuple[str, str]:
    """
    :return: redirect_url, authenticity_token
    """
    soup = BeautifulSoup(html, "lxml")
    redirect_url = soup.find("a", text="click here to continue").get("href")
    authenticity_token = soup.find("input", attrs={"name": "authenticity_token"}).get("value")
    return redirect_url, authenticity_token


def remove_at_sign(username: str) -> str:
    if username.startswith("@"):
        return username[1:]
    return username
