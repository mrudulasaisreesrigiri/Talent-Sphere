import os
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Centralized Root .env resolution
app_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
backend_dir = os.path.dirname(app_dir)
root_dir = os.path.dirname(backend_dir)
root_env_path = os.path.join(root_dir, ".env")

if os.path.exists(root_env_path):
    load_dotenv(dotenv_path=root_env_path, override=True)
else:
    load_dotenv()

class Settings(BaseSettings):
    PROJECT_NAME: str = "Talent Management Platform for Employee Performance and Career Growth"
    ENV: str = "development"
    PORT: int = 8000
    SECRET_KEY: str = "talent-sphere-elevate-super-secret-key-change-in-production-32bytes"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 480

    # Database
    DB_HOST: str = "localhost"
    DB_PORT: int = 3306
    DB_USER: str = "root"
    DB_PASSWORD: str = "password"
    DB_NAME: str = "talent_sphere_elevate"
    DATABASE_URL: str = "sqlite:///./talent_sphere_elevate.db"

    # ChromaDB
    CHROMA_PERSIST_DIR: str = "./chroma_db"

    # Groq API
    GROQ_API_KEY: str = ""
    GROQ_MODEL: str = "openai/gpt-oss-120b"

    # Uploads
    UPLOAD_DIR: str = "./uploads"
    MAX_FILE_SIZE_MB: int = 50

    # Email / SMTP Service Configuration
    SMTP_HOST: str = "smtp.gmail.com"
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_PASS: str = ""
    SMTP_USE_TLS: bool = True
    SMTP_FROM_EMAIL: str = ""
    SMTP_FROM_NAME: str = "Talent Management Platform for Employee Performance and Career Growth"

    def get_smtp_user(self) -> str:
        return (self.SMTP_USER or self.SMTP_USERNAME or os.getenv("SMTP_USER") or os.getenv("SMTP_USERNAME") or "").strip()

    def get_smtp_password(self) -> str:
        return (self.SMTP_PASSWORD or self.SMTP_PASS or os.getenv("SMTP_PASSWORD") or os.getenv("SMTP_PASS") or "").strip()

    def get_smtp_host(self) -> str:
        return (self.SMTP_HOST or os.getenv("SMTP_HOST") or "smtp.gmail.com").strip()

    def get_smtp_port(self) -> int:
        val = os.getenv("SMTP_PORT", str(self.SMTP_PORT or 587)).strip()
        try:
            return int(val)
        except ValueError:
            return 587

    def get_smtp_from_email(self) -> str:
        from_email = (self.SMTP_FROM_EMAIL or os.getenv("SMTP_FROM_EMAIL") or "").strip()
        if not from_email:
            from_email = self.get_smtp_user()
        return from_email or "support@talentsphere.com"

    def get_smtp_from_name(self) -> str:
        return (self.SMTP_FROM_NAME or os.getenv("SMTP_FROM_NAME") or "Talent Management Platform for Employee Performance and Career Growth").strip()

    def get_smtp_use_tls(self) -> bool:
        env_tls = os.getenv("SMTP_USE_TLS") or os.getenv("SMTP_TLS")
        if env_tls is not None:
            return env_tls.strip().lower() in ("true", "1", "yes")
        return bool(self.SMTP_USE_TLS)

    class Config:
        env_file = root_env_path if os.path.exists(root_env_path) else ".env"
        env_file_encoding = "utf-8"
        extra = "ignore"

    def get_database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return "sqlite:///./talent_sphere_elevate.db"

settings = Settings()

os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
os.makedirs(settings.CHROMA_PERSIST_DIR, exist_ok=True)
