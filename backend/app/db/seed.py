from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.db.base import Base
from app.db.models import Booking, MaintenanceTicket, Property, Provider
from app.db.session import SessionLocal, engine
from app.schemas.common import ProviderCategory, ReportedByRole, TicketStatus, TicketUrgency


def run_seed(db: Session | None = None) -> dict[str, int]:
    """Popula dados iniciais de demonstração de forma idempotente."""
    close_at_end = False
    if db is None:
        Base.metadata.create_all(bind=engine)
        db = SessionLocal()
        close_at_end = True

    try:
        # 1. Properties
        prop_copa_id = "prop-copacabana-01"
        prop_vila_id = "prop-vilamadalena-02"
        prop_gramado_id = "prop-gramado-03"

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
                    rules_faq=(
                        "Check-in a partir das 15h. Não fumar no interior do imóvel. "
                        "Silêncio após as 22h."
                    ),
                )
            )

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
                    rules_faq=(
                        "Check-in inteligente via fechadura eletrônica. "
                        "Proibidas festas e eventos com som alto."
                    ),
                )
            )

        if prop_gramado_id not in existing_props:
            db.add(
                Property(
                    id=prop_gramado_id,
                    name="Chalé Aconchegante Gramado",
                    description=(
                        "Chalé alpino com lareira ecológica, hidromassagem e calefação, "
                        "cercado pela natureza da Serra Gaúcha."
                    ),
                    address="Rua das Hortênsias, 850 - Planalto",
                    city="Gramado",
                    state="RS",
                    rules_faq=(
                        "Lareira com lenha disponibilizada na garagem. "
                        "Pets de pequeno porte são bem-vindos."
                    ),
                )
            )

        db.flush()

        # 2. Bookings (Agenda de reservas com dias ocupados e livres)
        today = date.today()
        existing_bookings_count = db.query(Booking).count()
        if existing_bookings_count == 0:
            db.add_all(
                [
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
                    # Gramado: Reserva ativa encerrando amanhã
                    Booking(
                        id="book-gramado-current",
                        property_id=prop_gramado_id,
                        guest_name="Beatriz Mendonça",
                        guest_contact="+55 (54) 98111-2233",
                        start_date=today - timedelta(days=4),
                        end_date=today + timedelta(days=1),
                        status="active",
                    ),
                ]
            )

        # 3. Providers validados no DB (todas as categorias)
        existing_providers_count = db.query(Provider).count()
        if existing_providers_count == 0:
            db.add_all(
                [
                    Provider(
                        id="prov-encanador-01",
                        name="Mario Encanamentos Rápidos",
                        category=ProviderCategory.PLUMBER.value,
                        region="Rio de Janeiro - Zona Sul",
                        phone="+55 (21) 98888-1111",
                        is_validated=True,
                        rating=4.9,
                        source="google_places",
                    ),
                    Provider(
                        id="prov-eletricista-01",
                        name="Volts & Watts Elétrica Segura",
                        category=ProviderCategory.ELECTRICIAN.value,
                        region="Rio de Janeiro - Zona Sul",
                        phone="+55 (21) 97777-2222",
                        is_validated=True,
                        rating=4.8,
                        source="google_places",
                    ),
                    Provider(
                        id="prov-pintor-01",
                        name="Cores Vivas Pintura Imobiliária",
                        category=ProviderCategory.PAINTER.value,
                        region="São Paulo - Zona Oeste",
                        phone="+55 (11) 96666-3333",
                        is_validated=True,
                        rating=5.0,
                        source="google_places",
                    ),
                    Provider(
                        id="prov-organizador-01",
                        name="Harmonia Casa & Organização",
                        category=ProviderCategory.ORGANIZER.value,
                        region="São Paulo - Zona Oeste",
                        phone="+55 (11) 95555-4444",
                        is_validated=True,
                        rating=4.9,
                        source="fixture",
                    ),
                    Provider(
                        id="prov-geral-01",
                        name="Faz-Tudo Serra Reparos Gerais",
                        category=ProviderCategory.GENERAL_MAINTENANCE.value,
                        region="Gramado - Serra Gaúcha",
                        phone="+55 (54) 94444-5555",
                        is_validated=True,
                        rating=4.7,
                        source="google_places",
                    ),
                    Provider(
                        id="prov-encanador-02",
                        name="HidroFix Desentupidora e Tubulações",
                        category=ProviderCategory.PLUMBER.value,
                        region="Rio de Janeiro - Zona Sul",
                        phone="+55 (21) 93333-6666",
                        is_validated=True,
                        rating=4.6,
                        source="fixture",
                    ),
                ]
            )

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
