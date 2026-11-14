"""The fixed vocabularies of the spec's Data model."""

from enum import StrEnum


class Status(StrEnum):
    SAVED = "saved"
    APPLIED = "applied"
    SCREEN = "screen"
    INTERVIEW = "interview"
    OFFER = "offer"
    REJECTED = "rejected"
    GHOSTED = "ghosted"


class Source(StrEnum):
    COLD = "cold"
    INBOUND = "inbound"
    REFERRAL = "referral"
