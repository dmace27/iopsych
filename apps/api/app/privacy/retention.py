"""Scheduler entry point for bounded cross-organization retention cleanup."""

from app.database.session import create_database_engine, create_session_factory
from app.privacy.config import PrivacySettings
from app.privacy.service import PrivacyService


def main() -> None:
    """Anonymize one configured batch and print a non-identifying summary."""

    settings = PrivacySettings()
    factory = create_session_factory(create_database_engine())
    with factory() as session:
        result = PrivacyService(session, settings).run_retention()
    print(f"Retention complete: {len(result.anonymized_assessment_ids)} assessments anonymized")


if __name__ == "__main__":  # pragma: no cover - exercised by deployment scheduler
    main()
