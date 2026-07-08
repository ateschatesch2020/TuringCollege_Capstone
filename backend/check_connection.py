from dotenv import load_dotenv
import requests
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def check_connection():
    load_dotenv()
    header = {"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"}
    url = "https://openrouter.ai/api/v1/models/user"
    try:
        response = requests.get(url, headers=header)
        response.raise_for_status()
        data = response.json()["data"]
        logger.info(data)
    except (requests.RequestException, KeyError) as e:
        logger.error("Connection check failed: %s", e)


if __name__ == "__main__":
    check_connection()