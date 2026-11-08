from datetime import date, timedelta

from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import Booking, MaintenanceTicket, Property, Provider
from app.db.session import SessionLocal, engine
from app.schemas.common import ProviderCategory, ReportedByRole, TicketStatus, TicketUrgency
from app.services.provider_collector import REGIONAL_MAPS_DIRECTORY
from app.services.provider_identity import provider_identity


def _ensure_schema_columns(db: Session) -> None:
    """Garante de forma idempotente que colunas novas existam em bancos preexistentes."""
    try:
        bind = db.get_bind()
        inspector = inspect(bind)
        tables = set(inspector.get_table_names())

        if "providers" in tables:
            columns = {c["name"] for c in inspector.get_columns("providers")}
            if "identity_key" not in columns:
                db.execute(text("ALTER TABLE providers ADD COLUMN identity_key VARCHAR(64)"))
            # Não remove histórico nem altera vínculos de cotações existentes.
            rows = (
                db.execute(
                    text(
                        "SELECT id, category, region, phone, identity_key FROM providers "
                        "ORDER BY is_validated DESC, created_at, id"
                    )
                )
                .mappings()
                .all()
            )
            seen = set()
            for row in rows:
                key = provider_identity(row["category"], row["region"], row["phone"])
                if key in seen:
                    db.execute(
                        text(
                            "UPDATE providers SET is_validated=false, identity_key=NULL "
                            "WHERE id=:id"
                        ),
                        {"id": row["id"]},
                    )
                else:
                    seen.add(key)
                    db.execute(
                        text("UPDATE providers SET identity_key=:key WHERE id=:id"),
                        {"key": key, "id": row["id"]},
                    )
            db.execute(
                text(
                    "CREATE UNIQUE INDEX IF NOT EXISTS uq_provider_identity "
                    "ON providers(identity_key)"
                )
            )

        if "properties" in tables:
            prop_cols = {c["name"] for c in inspector.get_columns("properties")}
            if "nightly_rate" not in prop_cols:
                alter_sql = (
                    "ALTER TABLE properties ADD COLUMN nightly_rate FLOAT NOT NULL DEFAULT 350.0"
                )
                db.execute(text(alter_sql))

        if "bookings" in tables:
            book_cols = {c["name"] for c in inspector.get_columns("bookings")}
            if "total_price" not in book_cols:
                db.execute(text("ALTER TABLE bookings ADD COLUMN total_price FLOAT"))
            if "num_guests" not in book_cols:
                db.execute(
                    text("ALTER TABLE bookings ADD COLUMN num_guests INTEGER NOT NULL DEFAULT 2")
                )
            if "rejection_reason" not in book_cols:
                db.execute(text("ALTER TABLE bookings ADD COLUMN rejection_reason TEXT"))
            if "session_id" not in book_cols:
                db.execute(text("ALTER TABLE bookings ADD COLUMN session_id VARCHAR(100)"))

        if "providers" in tables:
            prov_cols = {c["name"] for c in inspector.get_columns("providers")}
            if "reviews_count" not in prov_cols:
                db.execute(
                    text(
                        "ALTER TABLE providers ADD COLUMN reviews_count INTEGER NOT NULL DEFAULT 42"
                    )
                )
            if "address" not in prov_cols:
                db.execute(text("ALTER TABLE providers ADD COLUMN address VARCHAR(220)"))

        if "maintenance_tickets" in tables:
            ticket_cols = {c["name"] for c in inspector.get_columns("maintenance_tickets")}
            if "adm_synthesis" not in ticket_cols:
                db.execute(text("ALTER TABLE maintenance_tickets ADD COLUMN adm_synthesis TEXT"))

        db.commit()
    except Exception:
        db.rollback()


def run_seed(db: Session | None = None) -> dict[str, int]:
    """Popula dados iniciais de demonstração de forma idempotente."""
    close_at_end = False
    if db is None:
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        close_at_end = True
    else:
        Base.metadata.create_all(bind=db.get_bind())

    try:
        _ensure_schema_columns(db)

        # 1. Properties (3 imóveis selecionados para o grid 1x3)
        prop_copa_id = "prop-copacabana-01"
        prop_vila_id = "prop-vilamadalena-02"
        prop_recife_id = "prop-portodigital-04"

        existing_props = {p.id: p for p in db.query(Property).all()}

        if prop_copa_id not in existing_props:
            db.add(
                Property(
                    id=prop_copa_id,
                    name="Apartamento Vista Mar - Copacabana",
                    description=(
                        "Apartamento amplo de 2 quartos com vista panorâmica para o mar, "
                        "ar-condicionado em todos os cômodos e cozinha equipada."
                    ),
                    address="Av. Atlântica, 1702 - Copacabana",
                    city="Rio de Janeiro",
                    state="RJ",
                    nightly_rate=420.0,
                    rules_faq=(
                        "Check-in a partir das 15h. Não fumar no interior do imóvel. "
                        "Silêncio após as 22h."
                    ),
                )
            )
        else:
            existing_props[prop_copa_id].nightly_rate = 420.0

        if prop_vila_id not in existing_props:
            db.add(
                Property(
                    id=prop_vila_id,
                    name="Loft Moderno Vila Madalena",
                    description=(
                        "Loft moderno com pé-direito duplo, varanda gourmet, Wi-Fi veloz e "
                        "espaço home-office ideal para nômades digitais."
                    ),
                    address="Rua Girassol, 420 - Vila Madalena",
                    city="São Paulo",
                    state="SP",
                    nightly_rate=350.0,
                    rules_faq=(
                        "Check-in inteligente via fechadura eletrônica. "
                        "Proibidas festas e eventos com som alto."
                    ),
                )
            )
        else:
            existing_props[prop_vila_id].nightly_rate = 350.0

        if prop_recife_id not in existing_props:
            db.add(
                Property(
                    id=prop_recife_id,
                    name="Studio Tech Porto Digital - Recife Antigo",
                    description=(
                        "Studio moderno e tecnológico no coração do Porto Digital, a 200m do "
                        "Marco Zero e dos armazéns criativos do Recife Antigo. Equipado com "
                        "internet dedicada de 500Mbps, workstation com monitor externo, "
                        "fechadura inteligente 24h, ar-condicionado inverter silencioso "
                        "e vista para o Rio Capibaribe. Perfeito para nômades digitais, "
                        "imersões de tecnologia, "
                        "hackathons ou estadias produtivas de final de semana."
                    ),
                    address="Cais do Apolo, 222 - Bairro do Recife",
                    city="Recife",
                    state="PE",
                    nightly_rate=290.0,
                    rules_faq=(
                        "Check-in autônomo 24h via fechadura digital inteligente com token. "
                        "Wi-Fi dedicado ultra-rápido (SSID: PortoDigital_Tech, 500Mbps simétrico). "
                        "Silêncio após as 22h. Não fumar no interior do estúdio. "
                        "Pets de pequeno porte são bem-vindos."
                    ),
                )
            )
        else:
            existing_props[prop_recife_id].nightly_rate = 290.0

        db.flush()

        # 2. Bookings (Agenda de reservas com dias ocupados e livres)
        today = date.today()
        existing_booking_ids = {b.id for b in db.query(Booking.id).all()}
        all_seed_bookings = [
            # Copacabana: Hóspede presente hoje até +3 dias; próxima reserva em +7 dias
            Booking(
                id="book-copa-current",
                property_id=prop_copa_id,
                guest_name="Carlos Drummond",
                guest_contact="+55 (21) 98765-4321",
                start_date=today - timedelta(days=2),
                end_date=today + timedelta(days=3),
                status="active",
                notes="Hóspede em viagem com a família.",
            ),
            Booking(
                id="book-copa-future",
                property_id=prop_copa_id,
                guest_name="Mariana Rios",
                guest_contact="+55 (21) 99123-8877",
                start_date=today + timedelta(days=7),
                end_date=today + timedelta(days=12),
                status="confirmed",
                notes="Check-in confirmado para o feriado.",
            ),
            # Vila Madalena: Imóvel livre hoje; reserva começa daqui a 4 dias
            Booking(
                id="book-vila-future",
                property_id=prop_vila_id,
                guest_name="Felipe Neto",
                guest_contact="+55 (11) 97788-9900",
                start_date=today + timedelta(days=4),
                end_date=today + timedelta(days=10),
                status="confirmed",
            ),
            # Recife - Porto Digital: Livre hoje; reserva de imersão tech em 5 dias
            Booking(
                id="book-recife-future",
                property_id=prop_recife_id,
                guest_name="Lucas Porto",
                guest_contact="+55 (81) 98765-1122",
                start_date=today + timedelta(days=5),
                end_date=today + timedelta(days=8),
                status="confirmed",
                notes="Hóspede em imersão de inovação no Porto Digital.",
            ),
        ]
        for b in all_seed_bookings:
            if b.id not in existing_booking_ids:
                db.add(b)

        # 3. Providers validados no DB (3 por categoria e cidade com nota, avaliações e endereço)
        db.query(Provider).filter(
            (Provider.source != "web_maps") | (Provider.name.like("Prestador simulado%"))
        ).delete(synchronize_session=False)
        db.flush()

        existing_providers_by_id = {p.id: p for p in db.query(Provider).all()}
        existing_providers_by_phone = {p.phone: p for p in existing_providers_by_id.values()}

        city_region_labels = {
            "rio de janeiro": "Rio de Janeiro - Zona Sul",
            "são paulo": "São Paulo - Zona Oeste",
            "recife": "Recife - Bairro do Recife",
        }

        for city_key, categories_map in REGIONAL_MAPS_DIRECTORY.items():
            region_label = city_region_labels.get(city_key, city_key.title())
            for cat, entries in categories_map.items():
                for entry in entries:
                    prov_id = str(entry["id"])
                    phone = str(entry["phone"])
                    existing_prov = existing_providers_by_id.get(
                        prov_id
                    ) or existing_providers_by_phone.get(phone)
                    identity = provider_identity(cat.value, region_label, phone)
                    if existing_prov is not None:
                        existing_prov.name = str(entry["name"])
                        existing_prov.category = cat.value
                        existing_prov.region = region_label
                        existing_prov.rating = float(str(entry["rating"]))
                        existing_prov.reviews_count = int(str(entry["reviews_count"]))
                        existing_prov.address = str(entry["address"])
                        existing_prov.is_validated = True
                        existing_prov.source = "web_maps"
                        existing_prov.identity_key = identity
                    else:
                        new_prov = Provider(
                            id=prov_id,
                            name=str(entry["name"]),
                            category=cat.value,
                            region=region_label,
                            phone=phone,
                            is_validated=True,
                            rating=float(str(entry["rating"])),
                            reviews_count=int(str(entry["reviews_count"])),
                            address=str(entry["address"]),
                            source="web_maps",
                            identity_key=identity,
                        )
                        db.add(new_prov)
                        existing_providers_by_id[prov_id] = new_prov
                        existing_providers_by_phone[phone] = new_prov

        # 4. Demonstração de Ticket Inicial
        existing_tickets_count = db.query(MaintenanceTicket).count()
        if existing_tickets_count == 0:
            db.add(
                MaintenanceTicket(
                    id="ticket-demo-01",
                    run_id="run-demo-seed-001",
                    property_id=prop_copa_id,
                    reported_by_role=ReportedByRole.TENANT.value,
                    category=ProviderCategory.PLUMBER.value,
                    urgency=TicketUrgency.URGENT.value,
                    location_in_property="Cozinha - Debaixo da pia",
                    description=(
                        "Vazamento contínuo no sifão da pia da cozinha, "
                        "escorrendo água para o armário."
                    ),
                    status=TicketStatus.OPEN.value,
                    notify_tenant=True,
                )
            )

        db.commit()

        counts = {
            "properties": db.query(Property).count(),
            "bookings": db.query(Booking).count(),
            "providers": db.query(Provider).count(),
            "tickets": db.query(MaintenanceTicket).count(),
        }
        return counts
    finally:
        if close_at_end:
            db.close()


if __name__ == "__main__":
    print("Iniciando seed do banco de dados...")
    results = run_seed()
    print("Seed concluído com sucesso:", results)
