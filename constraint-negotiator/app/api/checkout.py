from __future__ import annotations

import logging
from typing import Any, Literal

from fastapi import (
    APIRouter,
    HTTPException,
)
from pydantic import (
    BaseModel,
    Field,
)

from app.tutu.client import (
    TutuMCPClient,
    TutuMCPError,
)


logger = logging.getLogger(
    "constraint_negotiator.checkout"
)


router = APIRouter(
    prefix="/api/v1/negotiator",
    tags=["checkout"],
)


SUPPORTED_PRODUCTS = {
    "avia",
    "rail",
    "railway",
    "etrain",
    "bus",
    "hotels",
}


READY_KINDS = {
    "deeplink",
    "checkout_deeplink",
}


class CheckoutRequest(BaseModel):
    """
    Opaque checkout_ref received from a Tutu MCP
    search result.

    The object must be forwarded without rebuilding
    or changing its internal fields.
    """

    checkout_ref: dict[
        str,
        Any,
    ] = Field(
        min_length=1,
    )


class CheckoutResponse(BaseModel):
    status: Literal[
        "ready",
        "fallback",
    ]

    provider: Literal[
        "tutu"
    ] = "tutu"

    kind: str

    primary_url: str

    checkout_url: (
        str
        | None
    ) = None

    search_results_url: (
        str
        | None
    ) = None

    fallback_note: (
        str
        | None
    ) = None


@router.post(
    "/checkout",
    response_model=CheckoutResponse,
)
async def create_checkout(
    request: CheckoutRequest,
) -> CheckoutResponse:
    checkout_ref = dict(
        request.checkout_ref
    )

    _validate_checkout_ref(
        checkout_ref
    )

    client = TutuMCPClient()

    try:
        payload = await client.call_tool(
            name=(
                "create_checkout_link"
            ),
            arguments=checkout_ref,
        )

    except TutuMCPError as exc:
        logger.warning(
            (
                "checkout_tool_failed "
                "error_type=%s"
            ),
            type(exc).__name__,
        )

        raise HTTPException(
            status_code=502,
            detail=(
                "Tutu could not create "
                "a checkout link for "
                "this offer"
            ),
        ) from exc

    except Exception as exc:
        logger.exception(
            "checkout_mcp_unavailable"
        )

        raise HTTPException(
            status_code=503,
            detail=(
                "Tutu MCP is temporarily "
                "unavailable"
            ),
        ) from exc

    return _to_checkout_response(
        payload
    )


def _validate_checkout_ref(
    checkout_ref: dict[
        str,
        Any,
    ],
) -> None:
    product_type = (
        checkout_ref.get(
            "product_type"
        )
        or checkout_ref.get(
            "transport"
        )
    )

    if not isinstance(
        product_type,
        str,
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "checkout_ref must contain "
                "product_type or transport"
            ),
        )

    if (
        product_type
        not in SUPPORTED_PRODUCTS
    ):
        raise HTTPException(
            status_code=422,
            detail=(
                "Unsupported checkout "
                f"product: {product_type}"
            ),
        )


def _to_checkout_response(
    payload: dict[
        str,
        Any,
    ],
) -> CheckoutResponse:
    kind = payload.get(
        "kind"
    )

    if not isinstance(
        kind,
        str,
    ) or not kind.strip():
        raise HTTPException(
            status_code=502,
            detail=(
                "Tutu checkout response "
                "does not contain kind"
            ),
        )

    checkout_url = (
        _optional_string(
            payload.get(
                "checkout_url"
            )
        )
    )

    search_results_url = (
        _optional_string(
            payload.get(
                "search_results_url"
            )
        )
    )

    fallback_note = (
        _optional_string(
            payload.get(
                "fallback_note"
            )
        )
    )

    primary_url = (
        _pick_primary_url(
            kind=kind,
            checkout_url=(
                checkout_url
            ),
            search_results_url=(
                search_results_url
            ),
        )
    )

    status: Literal[
        "ready",
        "fallback",
    ] = (
        "ready"
        if kind in READY_KINDS
        else "fallback"
    )

    return CheckoutResponse(
        status=status,
        kind=kind,
        primary_url=primary_url,
        checkout_url=checkout_url,
        search_results_url=(
            search_results_url
        ),
        fallback_note=(
            fallback_note
        ),
    )


def _pick_primary_url(
    *,
    kind: str,
    checkout_url: (
        str
        | None
    ),
    search_results_url: (
        str
        | None
    ),
) -> str:
    # For an avia search_redirect the tool
    # explicitly says the search page is the
    # correct user-facing fallback.
    if (
        kind
        == "search_redirect"
        and search_results_url
    ):
        return search_results_url

    if checkout_url:
        return checkout_url

    if search_results_url:
        return search_results_url

    raise HTTPException(
        status_code=502,
        detail=(
            "Tutu checkout response "
            "does not contain a usable URL"
        ),
    )


def _optional_string(
    value: Any,
) -> str | None:
    if not isinstance(
        value,
        str,
    ):
        return None

    clean = value.strip()

    if not clean:
        return None

    # IMPORTANT:
    # We return the original URL string,
    # not `clean`, because Tutu checkout
    # URLs are opaque and must not be
    # reconstructed or rewritten.
    return value