from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    # API Security
    api_key: str = "your-api-key-here"
    
    # Email Provider: "resend" or "smtp"
    email_provider: str = "resend"
    
    # Resend.com settings (free tier: 3000 emails/month)
    resend_api_key: str = ""
    resend_from_email: str = "onboarding@resend.dev"  # Default Resend domain
    
    # SMTP settings (Gmail example)
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""  # App password for Gmail
    smtp_from_email: str = ""
    
    # Rate limiting
    rate_limit: str = "5/minute"
    
    # CORS
    cors_origins: list = ["*"]
    
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()