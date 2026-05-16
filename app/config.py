from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=PROJECT_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    SECRET_KEY: str = "dev-secret-change-me"
    TEACHER_EMAIL: str = "teacher@example.com"

    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""

    MIN_ATTENDANCE_PCT: float = 80.0
    FACE_MATCH_THRESHOLD: float = 0.5
    LIVENESS_THRESHOLD: float = 0.7

    DATABASE_URL: str = f"sqlite:///{PROJECT_ROOT / 'attendance.db'}"

    ENROLLMENT_DIR: Path = PROJECT_ROOT / "enrollment_data"
    ID_CARDS_DIR: Path = PROJECT_ROOT / "id_cards"
    SPOOF_LOG_DIR: Path = PROJECT_ROOT / "spoof_log"


settings = Settings()

for directory in (settings.ENROLLMENT_DIR, settings.ID_CARDS_DIR, settings.SPOOF_LOG_DIR):
    directory.mkdir(exist_ok=True)
