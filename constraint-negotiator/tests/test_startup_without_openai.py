from __future__ import annotations

import os
import subprocess
import sys

from pathlib import Path


def test_service_starts_with_unavailable_trip_parser(
    tmp_path: Path,
) -> None:
    """
    TripParser must be initialized lazily.

    This test deliberately replaces TripParser with
    a parser that cannot be constructed.

    Expected behaviour:
    - importing FastAPI must still succeed;
    - /health must work;
    - non-AI routes must remain registered;
    - /parse must return HTTP 503;
    - the service must remain alive afterwards.

    This is intentionally independent of local .env
    loading so the test is deterministic.
    """

    repo_root = (
        Path(__file__)
        .resolve()
        .parents[1]
    )

    env = os.environ.copy()

    existing_pythonpath = env.get(
        "PYTHONPATH",
        "",
    )

    env["PYTHONPATH"] = (
        str(repo_root)
        if not existing_pythonpath
        else (
            str(repo_root)
            + os.pathsep
            + existing_pythonpath
        )
    )

    code = r'''
from fastapi.testclient import TestClient

import app.ai.parser as parser_module


# ---------------------------------------------------------
# Sentinel parser
#
# If the application creates TripParser during import,
# importing app.main will fail immediately.
#
# If initialization is truly lazy, app.main imports
# normally and this error appears only when /parse is used.
# ---------------------------------------------------------

class UnavailableTripParser:
    def __init__(
        self,
        *args,
        **kwargs,
    ) -> None:
        raise RuntimeError(
            "OPENAI_API_KEY is required "
            "for natural-language trip parsing"
        )


parser_module.TripParser = (
    UnavailableTripParser
)

parser_module.get_trip_parser.cache_clear()


# ---------------------------------------------------------
# Application import
# ---------------------------------------------------------

from app.main import app


client = TestClient(app)


# ---------------------------------------------------------
# Service startup
# ---------------------------------------------------------

health = client.get(
    "/health"
)

assert (
    health.status_code
    == 200
), (
    health.status_code,
    health.text,
)

assert (
    health.json()["status"]
    == "ok"
)


# ---------------------------------------------------------
# Public API must still exist
# ---------------------------------------------------------

openapi = app.openapi()

paths = set(
    openapi.get(
        "paths",
        {}
    )
)

required_paths = {
    "/api/v1/negotiator/checkout",
    "/api/v1/negotiator/from-spec",
    "/api/v1/negotiator/products/search",
    "/api/v1/negotiator/parse",
    "/api/v1/negotiator/from-text",
    "/health",
}

missing_paths = (
    required_paths
    - paths
)

assert not missing_paths, (
    "Missing API paths: "
    f"{sorted(missing_paths)}"
)


# ---------------------------------------------------------
# Natural-language parsing must fail gracefully
# ---------------------------------------------------------

parse_response = client.post(
    "/api/v1/negotiator/parse",
    json={
        "text": (
            "Хочу завтра "
            "из Москвы в Казань"
        )
    },
)

assert (
    parse_response.status_code
    == 503
), (
    parse_response.status_code,
    parse_response.text,
)

parse_payload = (
    parse_response.json()
)

assert (
    "OPENAI_API_KEY"
    in str(
        parse_payload.get(
            "detail",
            ""
        )
    )
)


# ---------------------------------------------------------
# Failed AI request must NOT kill the service
# ---------------------------------------------------------

health_after = client.get(
    "/health"
)

assert (
    health_after.status_code
    == 200
), (
    health_after.status_code,
    health_after.text,
)

assert (
    health_after.json()["status"]
    == "ok"
)


print(
    "lazy-trip-parser: OK"
)
'''

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            code,
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert (
        result.returncode
        == 0
    ), (
        "\nSTDOUT:\n"
        + result.stdout
        + "\nSTDERR:\n"
        + result.stderr
    )

    assert (
        "lazy-trip-parser: OK"
        in result.stdout
    )