import requests
import time
import os
import src.infrastructure.utils.config as config
from pathlib import Path
config= config.AppConfig.from_env()
token = config.mineru.api_token
url = f"https://mineru.net/api/v4/extract-results/batch/6745f16c-ae52-45a1-b7df-5df9cb1569bf"
header = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {token}"
}

res = requests.get(url, headers=header)
print(res.status_code)
print(res.json())
print(res.json()["data"])