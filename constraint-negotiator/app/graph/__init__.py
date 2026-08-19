from __future__ import annotations

from typing import Any


__all__ = [
    "build_negotiator_graph",
    "negotiator_graph",
]


def __getattr__(
    name: str,
) -> Any:
    """
    Backward-compatible lazy exports.

    The graph package itself must stay free of
    runtime side effects. In particular, importing
    app.graph must never create TripParser and must
    never require OPENAI_API_KEY.

    Natural-language parsing is initialized lazily
    inside app.graph.builder only when a text request
    actually needs it.
    """

    if name == "build_negotiator_graph":
        from app.graph.builder import (
            build_negotiator_graph,
        )

        return build_negotiator_graph

    if name == "negotiator_graph":
        from app.graph.builder import (
            negotiator_graph,
        )

        return negotiator_graph

    raise AttributeError(
        f"module {__name__!r} "
        f"has no attribute {name!r}"
    )
