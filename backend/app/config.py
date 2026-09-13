from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "postgresql+psycopg2://provenance:provenance@localhost:54373/provenance"
    jwt_secret: str = "experiment-provenance-dev-secret"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 12


settings = Settings()
