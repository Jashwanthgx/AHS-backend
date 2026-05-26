from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict

# Automatically finds the absolute path of your main root folder (AHS-backend)
BASE_DIR = Path(__file__).resolve().parent.parent

class Settings(BaseSettings):
    PROJECT_NAME: str
    DATABASE_URL: str
    
    # Define the new expected variables so Pydantic accepts them smoothly
    OPENAI_API_KEY: str
    GITHUB_TOKEN: str

    # Explicitly look exactly in the root directory for your .env file
    model_config = SettingsConfigDict(
        env_file=BASE_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore"  # Tells Pydantic not to crash if extra variables exist
    )

settings = Settings()