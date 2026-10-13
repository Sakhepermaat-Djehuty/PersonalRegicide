"""Regicide Legacy campaign: persistent party, missions, relics, mercenaries.

Content comes from docs/LEGACY_CAMPAIGN.md (fan transcription reconciled with the
rulebook); everything tagged "unverified" there is also tagged here so the UI can say so.
"""
from . import legacy_rules  # noqa: F401  (registers the rule sets)
from .state import CampaignState  # noqa: F401
