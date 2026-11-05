"""WSGI application. Use a hardened WSGI server and TLS gateway for deployment."""

import hmac
import json
import logging
from .engine import Engine
from .models import GatewayError, identifier

logger = logging.getLogger(__name__)


def strict_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON object key")
        result[key] = value
    return result


def reject_constant(value):
    raise ValueError("Nonstandard JSON constant")


class Application:
    def __init__(self, engine: Engine, credentials: dict[str, str]):
        if not credentials:
            raise ValueError("At least one credential is required")
        for token, tenant in credentials.items():
            if (
                not isinstance(token, str)
                or not 32 <= len(token) <= 512
                or not all(33 <= ord(char) <= 126 for char in token)
            ):
                raise ValueError(
                    "Tokens must be 32-512 printable non-whitespace ASCII characters"
                )
            identifier(tenant)
        self.engine = engine
        self.credentials = dict(credentials)

    def __call__(self, environ, start_response):
        headers = [
            ("Content-Type", "application/json"),
            ("Cache-Control", "no-store"),
            ("X-Content-Type-Options", "nosniff"),
        ]

        def send(status, body):
            data = json.dumps(body, ensure_ascii=False).encode()
            start_response(status, headers + [("Content-Length", str(len(data)))])
            return [data]

        path = environ.get("PATH_INFO", "")
        if path == "/healthz" and environ.get("REQUEST_METHOD") == "GET":
            return send("200 OK", {"status": "ok"})
        if path != "/v1/query":
            return send("404 Not Found", {"error": "not_found"})
        if environ.get("REQUEST_METHOD") != "POST":
            headers.append(("Allow", "POST"))
            return send("405 Method Not Allowed", {"error": "method_not_allowed"})
        authorization = environ.get("HTTP_AUTHORIZATION", "")
        supplied = (
            authorization.removeprefix("Bearer ")
            if authorization.startswith("Bearer ")
            else ""
        )
        tenant = None
        if supplied.isascii() and len(supplied) <= 512:
            for token, candidate in self.credentials.items():
                if hmac.compare_digest(supplied, token):
                    tenant = candidate
        if tenant is None:
            headers.append(("WWW-Authenticate", "Bearer"))
            return send("401 Unauthorized", {"error": "unauthorized"})
        try:
            if (
                environ.get("CONTENT_TYPE", "").split(";", 1)[0].strip()
                != "application/json"
            ):
                return send("415 Unsupported Media Type", {"error": "json_required"})
            if environ.get("HTTP_TRANSFER_ENCODING"):
                return send(
                    "400 Bad Request", {"error": "transfer_encoding_unsupported"}
                )
            length = int(environ.get("CONTENT_LENGTH") or "0")
            if not 0 < length <= 16384:
                return send("413 Content Too Large", {"error": "invalid_body_size"})
            raw = environ["wsgi.input"].read(length)
            if len(raw) != length:
                raise GatewayError("Incomplete request")
            body = json.loads(
                raw, object_pairs_hook=strict_object, parse_constant=reject_constant
            )
            if not isinstance(body, dict) or set(body) - {
                "question",
                "request_id",
                "top_k",
            }:
                raise GatewayError(
                    "Only question, request_id and top_k fields are accepted"
                )
            if not {"question", "request_id"} <= set(body):
                raise GatewayError("question and request_id are required")
            result = self.engine.query(tenant, **body)
            return send("200 OK", result)
        except GatewayError as exc:
            labels = {400: "Bad Request", 409: "Conflict", 429: "Too Many Requests"}
            if exc.status_code == 429:
                headers.append(("Retry-After", "60"))
            return send(
                f"{exc.status_code} {labels[exc.status_code]}", {"error": exc.code}
            )
        except (ValueError, TypeError, UnicodeError, RecursionError):
            return send("400 Bad Request", {"error": "invalid_request"})
        except Exception:
            # Deliberately omit exception values and request data from logs.
            logger.error("gateway_request_failed")
            return send("503 Service Unavailable", {"error": "service_unavailable"})


def from_environment():
    """Factory for an external WSGI server; refuse missing production configuration."""
    import os
    from .store import Store

    audit_key = os.environ.get("EVIDENCE_AUDIT_KEY", "")
    credentials = json.loads(
        os.environ.get("EVIDENCE_CREDENTIALS", "{}"),
        object_pairs_hook=strict_object,
        parse_constant=reject_constant,
    )
    if not isinstance(credentials, dict):
        raise ValueError("EVIDENCE_CREDENTIALS must be an object")
    store = Store(os.environ.get("EVIDENCE_DB", "var/evidence.db"))
    return Application(Engine(store, audit_key=audit_key.encode()), credentials)
