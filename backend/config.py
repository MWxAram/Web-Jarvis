from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    db_host: str = "localhost"
    db_port: int = 3306
    db_name: str = "jarvis_db"
    db_user: str = "root"
    db_password: str = ""

    jwt_secret: str = "dev_secret_change_in_production"
    jwt_algorithm: str = "HS256"
    jwt_access_expire_minutes: int = 60
    jwt_refresh_expire_days: int = 30

    # Все dev-origins уже в дефолте — даже без .env CORS будет работать
    cors_origins: str = (
        "http://localhost:3000,"
        "http://localhost:5500,"
        "http://127.0.0.1:5500,"
        "http://localhost:8080,"
        "http://127.0.0.1:8080"
    )

    app_title: str = "JARVIS Backend API"
    app_version: str = "0.7.0"
    # По умолчанию debug ВЫКЛЮЧЕН — иначе при отсутствующем/неполном .env
    # сервер по умолчанию отдаёт полные тексты исключений в ответах (500),
    # что раскрывает внутренние детали (пути, SQL, версии библиотек).
    # Включай DEBUG=true в .env только на локальной машине разработчика.
    debug: bool = False

    @property
    def db_url(self) -> str:
        return (
            f"mysql+pymysql://{self.db_user}:{self.db_password}"
            f"@{self.db_host}:{self.db_port}/{self.db_name}"
            f"?charset=utf8mb4"
        )

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


cfg = Settings()