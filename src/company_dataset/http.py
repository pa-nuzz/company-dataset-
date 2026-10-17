import threading
import time
from dataclasses import dataclass
from urllib.parse import urlsplit

import requests

USER_AGENT = "company-dataset/1.0 (open dataset builder; polite; identifies itself)"


class RequestError(Exception):
    pass


@dataclass
class HttpResponse:
    status: int
    text: str
    url: str

    def json(self):
        import json

        return json.loads(self.text)


class _HostThrottle:
    def __init__(self, interval: float, sleep):
        self.interval = interval
        self.sleep = sleep
        self.lock = threading.Lock()
        self.last = 0.0

    def wait(self):
        with self.lock:
            now = time.monotonic()
            delta = self.last + self.interval - now
            if delta > 0:
                self.sleep(delta)
            self.last = time.monotonic()


class HttpClient:
    RETRYABLE = {403, 429, 500, 502, 503, 504}

    def __init__(
        self,
        session=None,
        timeout: float = 20.0,
        max_attempts: int = 3,
        per_host_interval: float = 0.15,
        sleep=time.sleep,
        backoff_base: float = 1.5,
    ):
        self.session = session or requests.Session()
        if isinstance(self.session, requests.Session):
            self.session.headers["User-Agent"] = USER_AGENT
        self.timeout = timeout
        self.max_attempts = max_attempts
        self.per_host_interval = per_host_interval
        self.sleep = sleep
        self.backoff_base = backoff_base
        self._throttles: dict[str, _HostThrottle] = {}
        self._guard = threading.Lock()

    def _throttle(self, url: str) -> _HostThrottle:
        host = urlsplit(url).hostname or ""
        with self._guard:
            throttle = self._throttles.get(host)
            if throttle is None:
                throttle = _HostThrottle(self.per_host_interval, self.sleep)
                self._throttles[host] = throttle
            return throttle

    def get(self, url: str) -> HttpResponse:
        throttle = self._throttle(url)
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            throttle.wait()
            try:
                resp = self.session.get(url, timeout=self.timeout)
            except Exception as exc:
                last_error = exc
                if attempt < self.max_attempts:
                    self._backoff(attempt)
                    continue
                raise RequestError(str(exc)) from exc
            status = resp.status_code
            if status < 400 or status == 404:
                return HttpResponse(status, resp.text, resp.url)
            if status in self.RETRYABLE:
                if attempt < self.max_attempts:
                    self._backoff(attempt)
                    continue
                return HttpResponse(status, resp.text, resp.url)
            return HttpResponse(status, resp.text, resp.url)
        raise RequestError(str(last_error))

    def _backoff(self, attempt: int):
        import random

        self.sleep(self.backoff_base**attempt + random.random() * 0.5)
