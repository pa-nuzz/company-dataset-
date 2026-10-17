import json


class FakeResponse:
    def __init__(self, status, text="", url="fake://url"):
        self.status_code = status
        self.text = text
        self.url = url

    def json(self):
        return json.loads(self.text)


class FakeSession:
    def __init__(self, script=None, default_status=404):
        self.script = dict(script or {})
        self.calls = []
        self.default_status = default_status

    def get(self, url, timeout=None, **kwargs):
        self.calls.append(url)
        entry = self.script.get(url)
        if isinstance(entry, list):
            item = entry.pop(0) if entry else None
        else:
            item = entry
        if item is None:
            return FakeResponse(self.default_status, "", url)
        if isinstance(item, BaseException):
            raise item
        return item
