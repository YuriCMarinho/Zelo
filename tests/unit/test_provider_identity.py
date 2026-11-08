from unittest.mock import AsyncMock

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.models import Provider
from app.db.seed import _ensure_schema_columns
from app.schemas.common import ProviderCategory
from app.services.provider_collector import (
    ProviderCandidate,
    ProviderCollector,
    SimulatedContactGateway,
)


@pytest.mark.asyncio
async def test_formatted_phones_reuse_provider_and_allowlist(db_session):
    phones = ["+55 85 98888-1234", "+5585988881234"]
    source = AsyncMock()
    source.search.return_value = [
        ProviderCandidate(
            "same-business",
            "Mesmo prestador",
            ProviderCategory.PLUMBER,
            "Fortaleza, CE",
            p,
            "test",
        )
        for p in phones
    ]
    gateway = SimulatedContactGateway({phones[0]}, {"same-business": "Sim, confirmo."})
    result = await ProviderCollector(source, gateway).collect(
        db_session,
        ProviderCategory.PLUMBER,
        "Fortaleza, CE",
    )
    assert result.confirmed == 1
    assert result.skipped == 1
    assert db_session.query(Provider).count() == 1
    duplicate = Provider(
        name="Duplicata",
        category="plumber",
        region="fortaleza,  ce",
        phone="85988881234",
        is_validated=True,
    )
    db_session.add(duplicate)
    with pytest.raises(IntegrityError):
        db_session.commit()
    db_session.rollback()


def test_legacy_provider_migration_keeps_history_and_one_active_identity():
    engine = create_engine("sqlite:///:memory:")
    with Session(engine) as db:
        db.execute(
            text(
                "CREATE TABLE providers (id TEXT PRIMARY KEY, category TEXT, region TEXT, "
                "phone TEXT, is_validated BOOLEAN, created_at TEXT)"
            )
        )
        for provider_id, phone in [("a", "+55 85 98888-1234"), ("b", "+5585988881234")]:
            db.execute(
                text(
                    "INSERT INTO providers VALUES (:id, 'plumber', 'Fortaleza, CE', "
                    ":phone, true, '2026-01-01')"
                ),
                {"id": provider_id, "phone": phone},
            )
        db.commit()
        _ensure_schema_columns(db)
        _ensure_schema_columns(db)
        rows = db.execute(text("SELECT * FROM providers ORDER BY id")).mappings().all()
        assert len(rows) == 2  # IDs de históricos continuam válidos.
        assert rows[0]["identity_key"] is not None
        assert rows[0]["is_validated"]
        assert rows[1]["identity_key"] is None
        assert not rows[1]["is_validated"]
