"""Invented demo data for an empty database (spec: "Seed data", SEED_DEMO_DATA).

Every company is made up and every link points at example.com. Histories go through the
same service calls as the API, so the status rules set applied and follow-up dates.
"""

from dataclasses import dataclass, field
from datetime import date, timedelta

from app.domain import Source, Status
from app.repositories.base import Repository
from app.services.applications import change_status, create_application


@dataclass(frozen=True)
class _Step:
    status: Status
    days_ago: int
    note: str | None = None


@dataclass(frozen=True)
class _Demo:
    company: str
    role: str
    source: Source
    steps: list[_Step] = field(default_factory=list)
    link: str | None = None
    notes: str | None = None


S = Status

DEMO_APPLICATIONS: list[_Demo] = [
    _Demo("Bluefin Robotics", "ML Engineer", Source.COLD, link="https://example.com/jobs/bluefin-ml"),
    _Demo(
        "Quillmark Labs",
        "Data Scientist",
        Source.REFERRAL,
        [_Step(S.APPLIED, 12, "Referred by a former teammate")],
        notes="Small team, recommendation systems.",
    ),
    _Demo(
        "Harborlight Data",
        "MLOps Engineer",
        Source.INBOUND,
        [_Step(S.APPLIED, 9), _Step(S.SCREEN, 4, "30 min call with the recruiter")],
    ),
    _Demo(
        "Tessellate AI",
        "Senior ML Engineer",
        Source.COLD,
        [
            _Step(S.APPLIED, 20),
            _Step(S.SCREEN, 14),
            _Step(S.INTERVIEW, 7, "System design round"),
            _Step(S.OFFER, 2, "Offer received, deciding by Friday"),
        ],
        link="https://example.com/careers/tessellate-senior-mle",
    ),
    _Demo(
        "Copperleaf Systems",
        "Data Engineer",
        Source.COLD,
        [_Step(S.APPLIED, 25), _Step(S.REJECTED, 18, "Looking for more Spark experience")],
    ),
    _Demo(
        "Marigold Metrics",
        "Analytics Engineer",
        Source.INBOUND,
        [_Step(S.APPLIED, 40), _Step(S.GHOSTED, 10, "No reply after two follow-ups")],
    ),
    _Demo(
        "Driftwood Health",
        "ML Platform Engineer",
        Source.REFERRAL,
        [_Step(S.APPLIED, 15), _Step(S.SCREEN, 11), _Step(S.INTERVIEW, 5, "Take-home task sent")],
    ),
    _Demo(
        "Lanternfish Software",
        "Backend Engineer (Python)",
        Source.COLD,
        [_Step(S.APPLIED, 3)],
        link="https://example.com/jobs/lanternfish-backend",
    ),
    _Demo(
        "Pinecrest Logistics",
        "Forecasting Engineer",
        Source.INBOUND,
        [_Step(S.APPLIED, 30), _Step(S.SCREEN, 24), _Step(S.REJECTED, 20)],
    ),
    _Demo(
        "Saffron Vision",
        "Computer Vision Engineer",
        Source.COLD,
        notes="Read the team's blog before applying.",
    ),
]


def seed_if_empty(repo: Repository, today: date) -> int:
    """Creates the demo applications if there are none; returns how many were created.

    One transaction: a failure leaves the database empty, so the next start tries again.
    """
    with repo.transaction():
        if repo.list_applications():
            return 0
        for demo in DEMO_APPLICATIONS:
            application = create_application(
                repo,
                company=demo.company,
                role=demo.role,
                source=demo.source,
                link=demo.link,
                notes=demo.notes,
            )
            for step in demo.steps:
                change_status(
                    repo, application.id, step.status, step.note, today - timedelta(days=step.days_ago)
                )
    return len(DEMO_APPLICATIONS)
