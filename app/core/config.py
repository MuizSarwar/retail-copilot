from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables.

    Required fields have no default. If any required field is missing
    (e.g. DATABASE_URL, JWT_SECRET_KEY, GROQ_API_KEY), pydantic-settings
    raises a ValidationError and the application refuses to start.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Application
    app_name: str = "Retail Copilot"
    app_env: str = "development"
    port: int = 8000

    # Database (required)
    database_url: str

    # JWT authentication (required)
    jwt_secret_key: str
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 60

    # LLM (required)
    groq_api_key: str
    groq_model: str = "openai/gpt-oss-20b"

    # Embedding service
    embedding_service_url: str = "http://embedding:8001/embed"
    embedding_dimension: int = 384

    # Seed script credentials (required)
    seed_admin_email: str
    seed_admin_password: str
    seed_employee_email: str
    seed_employee_password: str


settings = Settings()
