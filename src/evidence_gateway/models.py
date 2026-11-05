"""Validated boundary objects. Tenant identity is never taken from a query body."""

from dataclasses import asdict, dataclass
import re

IDENTIFIER = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_.-]{0,79}$")


class GatewayError(Exception):
    status_code = 400
    code = "invalid_request"


class Conflict(GatewayError):
    status_code = 409
    code = "conflict"


class RateLimited(GatewayError):
    status_code = 429
    code = "rate_limited"


def identifier(value: str) -> str:
    if not isinstance(value, str) or not IDENTIFIER.fullmatch(value):
        raise GatewayError("Identifier must contain 1-80 letters, digits, _, . or -.")
    return value


@dataclass(frozen=True)
class Document:
    tenant: str
    id: str
    title: str
    text: str
    version: int = 1

    def __post_init__(self):
        identifier(self.tenant)
        identifier(self.id)
        if (
            not isinstance(self.title, str)
            or not self.title.strip()
            or len(self.title) > 200
        ):
            raise GatewayError("Title must contain 1-200 characters.")
        if (
            not isinstance(self.text, str)
            or not self.text.strip()
            or len(self.text) > 100_000
        ):
            raise GatewayError("Document text must contain 1-100000 characters.")
        if type(self.version) is not int or not 1 <= self.version <= 2**31 - 1:
            raise GatewayError("Version must be a positive 32-bit integer.")


@dataclass(frozen=True)
class Chunk:
    id: str
    document_id: str
    title: str
    text: str
    version: int


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float


@dataclass(frozen=True)
class Claim:
    chunk_id: str
    quote: str


@dataclass(frozen=True)
class Answer:
    request_id: str
    status: str
    answer: str
    citations: tuple[dict, ...]
    index_revision: str
    reason: str
    provider: str

    def to_dict(self):
        result = asdict(self)
        result["citations"] = list(self.citations)
        return result
