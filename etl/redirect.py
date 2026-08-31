import requests

headers = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/152.0.0.0 Safari/537.36"
    )
}

url = "https://moxby.com/marketplace/ai-content-detector?fpr=keith20&fp_sid=aitools"

response = requests.get(
    url,
    headers=headers,
    allow_redirects=True,
    timeout=10
)

print(response.status_code)
print(response.url)