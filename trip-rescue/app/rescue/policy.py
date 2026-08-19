from __future__ import annotations

from dataclasses import dataclass

from app.models.journey import JourneyOption
from app.models.rescue import RescueComponent


@dataclass(
    frozen=True,
    slots=True,
)
class RescuePolicy:
    """
    Product policy for rescue search.

    The goal is not to enumerate every mathematically
    possible rebuild, but to prefer minimal disruption.
    """

    max_budget_replacement_components: int = 2

    max_plans: int = 6

    allow_outbound_budget_replacement: bool = True
    allow_hotel_budget_replacement: bool = True
    allow_inbound_budget_replacement: bool = True

    def budget_components(
        self,
        *,
        journey: JourneyOption,
    ) -> list[RescueComponent]:

        result: list[
            RescueComponent
        ] = []

        if (
            self.allow_outbound_budget_replacement
        ):
            result.append(
                RescueComponent.OUTBOUND
            )

        if (
            self.allow_hotel_budget_replacement
            and journey.hotel is not None
        ):
            result.append(
                RescueComponent.HOTEL
            )

        if (
            self.allow_inbound_budget_replacement
        ):
            result.append(
                RescueComponent.INBOUND
            )

        return result