"""Email service with unlimited free provider rotation."""

import os
import json
import smtplib
import ssl
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from pathlib import Path
from typing import Optional
import resend

class UnlimitedEmailService:
    """Rotates through multiple free email providers for unlimited sends."""
    
    def __init__(self):
        self.data_file = Path("usage_data.json")
        self.usage_data = self._load_usage()
        
        self.providers = []
        
        # Resend: 3000/month free
        if os.getenv("RESEND_API_KEY"):
            self.providers.append({
                "name": "resend",
                "limit": 3000,
                "period": "month",
                "api_key": os.getenv("RESEND_API_KEY"),
                "sender": os.getenv("RESEND_SENDER", "onboarding@resend.dev")
            })
        
        # Gmail: 500/day free
        if os.getenv("GMAIL_USER") and os.getenv("GMAIL_PASS"):
            self.providers.append({
                "name": "gmail",
                "limit": 500,
                "period": "day",
                "host": "smtp.gmail.com",
                "port": 587,
                "user": os.getenv("GMAIL_USER"),
                "pass": os.getenv("GMAIL_PASS")
            })
        
        # Outlook: 300/day free
        if os.getenv("OUTLOOK_USER") and os.getenv("OUTLOOK_PASS"):
            self.providers.append({
                "name": "outlook",
                "limit": 300,
                "period": "day",
                "host": "smtp-mail.outlook.com",
                "port": 587,
                "user": os.getenv("OUTLOOK_USER"),
                "pass": os.getenv("OUTLOOK_PASS")
            })
        
        # Yahoo: 500/day free
        if os.getenv("YAHOO_USER") and os.getenv("YAHOO_PASS"):
            self.providers.append({
                "name": "yahoo",
                "limit": 500,
                "period": "day",
                "host": "smtp.mail.yahoo.com",
                "port": 587,
                "user": os.getenv("YAHOO_USER"),
                "pass": os.getenv("YAHOO_PASS")
            })
        
        # Zoho: 200/day free
        if os.getenv("ZOHO_USER") and os.getenv("ZOHO_PASS"):
            self.providers.append({
                "name": "zoho",
                "limit": 200,
                "period": "day",
                "host": "smtp.zoho.com",
                "port": 587,
                "user": os.getenv("ZOHO_USER"),
                "pass": os.getenv("ZOHO_PASS")
            })
        
        if not self.providers:
            # Fallback to single provider from config
            from config import get_settings
            settings = get_settings()
            if settings.resend_api_key:
                self.providers.append({
                    "name": "resend",
                    "limit": 3000,
                    "period": "month",
                    "api_key": settings.resend_api_key,
                    "sender": settings.resend_from_email or "onboarding@resend.dev"
                })
    
    def _load_usage(self) -> dict:
        if self.data_file.exists():
            with open(self.data_file, "r") as f:
                return json.load(f)
        return {}
    
    def _save_usage(self):
        with open(self.data_file, "w") as f:
            json.dump(self.usage_data, f)
    
    def _get_usage(self, name: str, period: str) -> int:
        now = datetime.now()
        key = f"{name}_{now.strftime('%Y-%m-%d') if period == 'day' else now.strftime('%Y-%m')}"
        return self.usage_data.get(key, 0)
    
    def _increment(self, name: str, period: str):
        now = datetime.now()
        key = f"{name}_{now.strftime('%Y-%m-%d') if period == 'day' else now.strftime('%Y-%m')}"
        self.usage_data[key] = self.usage_data.get(key, 0) + 1
        self._save_usage()
    
    def send_email(self, to_email: str, subject: str, body: str, from_name: str = None) -> dict:
        """Send email using available provider with automatic rotation."""
        
        for provider in self.providers:
            usage = self._get_usage(provider["name"], provider["period"])
            if usage >= provider["limit"]:
                continue
            
            try:
                if provider["name"] == "resend":
                    result = self._send_resend(provider, to_email, subject, body, from_name)
                else:
                    result = self._send_smtp(provider, to_email, subject, body, from_name)
                
                self._increment(provider["name"], provider["period"])
                result["usage"] = f"{usage + 1}/{provider['limit']}"
                return result
                
            except Exception as e:
                print(f"{provider['name']} failed: {e}, trying next...")
                continue
        
        return {"success": False, "error": "All providers at limit. Add more providers or wait for reset."}
    
    def _send_resend(self, provider: dict, to_email: str, subject: str, body: str, from_name: str = None) -> dict:
        resend.api_key = provider["api_key"]
        
        from_email = provider["sender"]
        if from_name:
            from_email = f"{from_name} <{from_email}>"
        
        is_html = '<' in body and '>' in body
        params = {
            "from": from_email,
            "to": [to_email],
            "subject": subject,
            "html" if is_html else "text": body
        }
        
        response = resend.Emails.send(params)
        return {"success": True, "message_id": response.get("id"), "provider": "resend"}
    
    def _send_smtp(self, provider: dict, to_email: str, subject: str, body: str, from_name: str = None) -> dict:
        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = f"{from_name or 'Notification'} <{provider['user']}>"
        msg["To"] = to_email
        
        msg.attach(MIMEText(body, "plain"))
        if '<' in body and '>' in body:
            msg.attach(MIMEText(body, "html"))
        
        context = ssl.create_default_context()
        with smtplib.SMTP(provider["host"], provider["port"]) as server:
            server.starttls(context=context)
            server.login(provider["user"], provider["pass"])
            server.sendmail(provider["user"], to_email, msg.as_string())
        
        return {"success": True, "provider": provider["name"]}
    
    def get_stats(self) -> dict:
        """Get usage stats for all providers."""
        stats = []
        for p in self.providers:
            usage = self._get_usage(p["name"], p["period"])
            stats.append({
                "provider": p["name"],
                "used": usage,
                "limit": p["limit"],
                "period": p["period"],
                "remaining": p["limit"] - usage
            })
        
        daily = sum(s["limit"] for s in stats if s["period"] == "day")
        monthly = sum(s["limit"] for s in stats if s["period"] == "month")
        
        return {
            "providers": stats,
            "capacity": {"daily": daily, "monthly": monthly + daily * 30}
        }

email_service = UnlimitedEmailService()
