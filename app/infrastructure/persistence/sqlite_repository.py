from sqlalchemy import String, Text, create_engine, select
from sqlalchemy.orm import DeclarativeBase, Mapped, Session, mapped_column

from app.application.ports.repository import OnboardingRepository
from app.domain.models import OnboardingState


class Base(DeclarativeBase):
    pass


class OnboardingRecord(Base):
    __tablename__ = "onboarding_state"

    onboarding_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    payload: Mapped[str] = mapped_column(Text, nullable=False)


class SQLiteOnboardingRepository(OnboardingRepository):
    def __init__(self, database_url: str):
        connect_args = {"check_same_thread": False} if database_url.startswith("sqlite") else {}
        self.engine = create_engine(database_url, connect_args=connect_args)
        Base.metadata.create_all(self.engine)

    def save(self, state: OnboardingState) -> None:
        payload = state.model_dump_json()
        with Session(self.engine) as session:
            record = session.get(OnboardingRecord, state.onboarding_id)
            if record is None:
                session.add(OnboardingRecord(onboarding_id=state.onboarding_id, payload=payload))
            else:
                record.payload = payload
            session.commit()

    def get(self, onboarding_id: str) -> OnboardingState | None:
        with Session(self.engine) as session:
            record = session.scalar(
                select(OnboardingRecord).where(OnboardingRecord.onboarding_id == onboarding_id)
            )
            if record is None:
                return None
            return OnboardingState.model_validate_json(record.payload)
