import json
import logging
from json import JSONDecodeError

import requests
from typing import Any
import perp.constants as constants 


logger = logging.getLogger(__name__)
class Error(Exception):
    pass

class ClientError(Error):
    def __init__(self, status_code, error_code, error_message, header, error_data=None):
        self.status_code = status_code
        self.error_code = error_code
        self.error_message = error_message
        self.header = header
        self.error_data = error_data


class ServerError(Error):
    def __init__(self, status_code, message):
        self.status_code = status_code
        self.message = message

class API:
    def __init__(
        self,
        proxies: dict = {}
    ):
        self.base_url = constants.HYPERLIQUID_MAINNET_API_URL
        self.session = requests.Session()
        self.session.headers.update(
            {
                "Content-Type": "application/json",
            }
        )
        self.proxies = proxies
        if self.proxies.get('https') or self.proxies.get('http'):
            self.session.proxies.update(self.proxies)

        self._logger = logging.getLogger(__name__)
        return

    def post(self, url_path: str, payload: Any = None) -> Any:
        if payload is None:
            payload = {}
        url = self.base_url + url_path

        response = self.session.post(url, json=payload)
        self._handle_exception(response)

        try:
            return response.json()
        except ValueError:
            return {"error": f"Could not parse JSON: {response.text}"}

    def _handle_exception(self, response):
        status_code = response.status_code
        if status_code < 400:
            return
        if 400 <= status_code < 500:
            try:
                err = json.loads(response.text)
            except JSONDecodeError:
                logger.error(response.text)
                raise ClientError(status_code, None, response.text, None, response.headers)
            error_data = None
            if "data" in err:
                error_data = err["data"]
            raise ClientError(status_code, err["code"], err["msg"], response.headers, error_data)
        raise ServerError(status_code, response.text)
