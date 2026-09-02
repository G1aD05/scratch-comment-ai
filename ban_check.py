import requests

proxies = {
    "http": "socks5h://127.0.0.1:9050",
    "https": "socks5h://127.0.0.1:9050",
}


def check():
    response = requests.get("https://scratch.mit.edu/login", proxies=proxies)

    if response.status_code == 403:
        return True
    else:
        return False
