from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_port: int = 8000
    anthropic_api_key: str = ""

    # mTLS proxy transport — all three must be set via .env to activate
    floodgate_cert: str = ""
    floodgate_key: str = ""
    floodgate_url: str = ""

    class Config:
        env_file = ".env"


settings = Settings()
