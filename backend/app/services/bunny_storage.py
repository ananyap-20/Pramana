"""Private Bunny Storage transport. Never expose credentials or follow redirects."""

import hashlib
import os
import re
import urllib.error
import urllib.request

from app.audit_models import AuditProblem


MAX_OBJECT_BYTES = 5 * 1024 * 1024 + 16


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class BunnyStorage:
    def __init__(self, host, zone, password):
        if not re.fullmatch(r"(?:(?:uk|ny|la|sg|se|br|jh|syd)\.)?storage\.bunnycdn\.com", host):
            raise ValueError("Use the Bunny Storage regional hostname, without https:// or a path.")
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,100}", zone) or not password or any(c in password for c in "\r\n"):
            raise ValueError("Invalid Bunny Storage zone or password configuration.")
        self.base, self.password = f"https://{host}/{zone}/", password
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())

    @classmethod
    def from_environment(cls):
        values = [os.getenv(k, "") for k in ("BUNNY_STORAGE_HOST", "BUNNY_STORAGE_ZONE", "BUNNY_STORAGE_PASSWORD")]
        if not any(values):
            return None
        if not all(values):
            raise ValueError("All three Bunny Storage settings are required.")
        return cls(*values)

    def request(self, method, key, content=None):
        if key and not re.fullmatch(r"pramana/[a-f0-9]{64}\.bin", key):
            raise ValueError("Invalid private storage object key.")
        headers = {"AccessKey": self.password, "Content-Type": "application/octet-stream"}
        if content is not None:
            if len(content) > MAX_OBJECT_BYTES:
                raise AuditProblem(413, "Retained file exceeds 5 MiB.")
            headers["Checksum"] = hashlib.sha256(content).hexdigest().upper()
        request = urllib.request.Request(self.base + key, data=content, headers=headers, method=method)
        try:
            with self.opener.open(request, timeout=20) as response:
                if method != "GET" or not key:
                    return b""
                body = response.read(MAX_OBJECT_BYTES + 1)
                if len(body) > MAX_OBJECT_BYTES:
                    raise AuditProblem(503, "Stored file exceeds its expected size.")
                return body
        except urllib.error.HTTPError as error:
            if method == "DELETE" and error.code == 404:
                return b""
            raise AuditProblem(503, "Private file storage is unavailable. Contact the operator.") from None
        except (urllib.error.URLError, OSError, TimeoutError):
            raise AuditProblem(503, "Private file storage is unavailable. Contact the operator.") from None

    def check_ready(self):
        self.request("GET", "")
