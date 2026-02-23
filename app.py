"""
FastAPI Email Service Application
Production-ready email API with rate limiting, authentication, and CORS support.
"""

import logging
import time
from typing import Optional, Dict, List
from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Header, Request, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, EmailStr, Field, validator

from config import get_settings, Settings
from email_service import email_service

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

settings = get_settings()

# Simple in-memory rate limiter
class RateLimiter:
    """Simple in-memory rate limiter per IP address."""
    
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.requests: Dict[str, List[float]] = defaultdict(list)
    
    def is_allowed(self, client_ip: str) -> tuple[bool, dict]:
        """Check if request is allowed and return rate limit info."""
        now = time.time()
        window_start = now - self.window_seconds
        
        # Clean old requests and count recent ones
        self.requests[client_ip] = [
            ts for ts in self.requests[client_ip] if ts > window_start
        ]
        
        current_count = len(self.requests[client_ip])
        
        if current_count >= self.max_requests:
            reset_time = min(self.requests[client_ip]) + self.window_seconds if self.requests[client_ip] else now
            return False, {
                "limit": self.max_requests,
                "remaining": 0,
                "reset": int(reset_time),
                "window": self.window_seconds
            }
        
        # Record this request
        self.requests[client_ip].append(now)
        
        return True, {
            "limit": self.max_requests,
            "remaining": self.max_requests - current_count - 1,
            "reset": int(now + self.window_seconds),
            "window": self.window_seconds
        }

# Initialize rate limiter
rate_limiter = RateLimiter(
    max_requests=settings.RATE_LIMIT_REQUESTS,
    window_seconds=settings.RATE_LIMIT_WINDOW
)


# Pydantic models
class EmailRequest(BaseModel):
    """Email request payload validation."""
    to_email: EmailStr = Field(..., description="Recipient email address")
    subject: str = Field(..., min_length=1, max_length=200, description="Email subject")
    body: str = Field(..., min_length=1, max_length=50000, description="Email body (HTML supported)")
    from_name: Optional[str] = Field(None, max_length=100, description="Optional sender display name")
    
    @validator("subject")
    def subject_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Subject cannot be empty")
        return v.strip()
    
    @validator("body")
    def body_not_empty(cls, v):
        if not v.strip():
            raise ValueError("Body cannot be empty")
        return v


class EmailResponse(BaseModel):
    """Email response model."""
    success: bool
    message: str
    provider: Optional[str] = None
    message_id: Optional[str] = None


class HealthResponse(BaseModel):
    """Health check response model."""
    status: str
    service: str
    timestamp: float
    email_provider: str


class ErrorResponse(BaseModel):
    """Error response model."""
    detail: str


# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    logger.info(f"Starting {settings.APP_NAME}")
    logger.info(f"Email provider: {settings.EMAIL_PROVIDER}")
    logger.info(f"Rate limit: {settings.RATE_LIMIT_REQUESTS} requests per {settings.RATE_LIMIT_WINDOW}s")
    yield
    logger.info(f"Shutting down {settings.APP_NAME}")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    description="Production-ready email sending API with rate limiting and authentication",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Dependency for API key authentication
async def verify_api_key(x_api_key: str = Header(..., alias="X-API-Key")):
    """Verify the API key from header."""
    if x_api_key != settings.API_KEY:
        logger.warning(f"Invalid API key attempt")
        raise HTTPException(
            status_code=401,
            detail="Invalid or missing API key"
        )
    return x_api_key


# Dependency for rate limiting
async def check_rate_limit(request: Request):
    """Check rate limit for the client IP."""
    # Get client IP (handle proxies)
    client_ip = request.headers.get("X-Forwarded-For", request.client.host)
    if client_ip and "," in client_ip:
        client_ip = client_ip.split(",")[0].strip()
    
    allowed, rate_info = rate_limiter.is_allowed(client_ip)
    
    if not allowed:
        logger.warning(f"Rate limit exceeded for IP: {client_ip}")
        raise HTTPException(
            status_code=429,
            detail=f"Rate limit exceeded. Try again in {rate_info['window']} seconds."
        )
    
    return rate_info


# Exception handler for email errors
@app.exception_handler(Exception)
async def exception_handler(request: Request, exc: Exception):
    """Handle general errors."""
    logger.error(f"Error: {str(exc)}")
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc), "success": False}
    )


# Health check endpoint
@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health_check():
    """
    Health check endpoint.
    Returns service status and configuration info.
    """
    return HealthResponse(
        status="healthy",
        service=settings.APP_NAME,
        timestamp=time.time(),
        email_provider=settings.EMAIL_PROVIDER
    )


# Send email endpoint
@app.post(
    "/send-email",
    response_model=EmailResponse,
    responses={
        400: {"model": ErrorResponse, "description": "Bad request"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        429: {"model": ErrorResponse, "description": "Rate limit exceeded"},
        500: {"model": ErrorResponse, "description": "Server error"}
    },
    tags=["Email"]
)
async def send_email(
    email_request: EmailRequest,
    api_key: str = Depends(verify_api_key),
    rate_info: dict = Depends(check_rate_limit)
):
    """
    Send an email to the specified recipient.
    
    - **to_email**: Recipient email address
    - **subject**: Email subject line
    - **body**: Email body content (HTML supported)
    - **from_name**: Optional sender display name
    
    Requires X-API-Key header for authentication.
    Rate limited to 5 requests per minute per IP.
    """
    try:
        result = email_service.send_email(
            to_email=email_request.to_email,
            subject=email_request.subject,
            body=email_request.body,
            from_name=email_request.from_name
        )
        
        if not result.get("success"):
            raise HTTPException(
                status_code=500,
                detail=result.get("error", "Failed to send email")
            )
        
        return EmailResponse(
            success=True,
            message=f"Email sent via {result.get('provider')}",
            provider=result.get("provider"),
            message_id=result.get("message_id")
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Unexpected error sending email: {str(e)}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to send email: {str(e)}"
        )


@app.get("/stats", tags=["Email"])
async def get_stats(api_key: str = Depends(verify_api_key)):
    """Get usage statistics for all configured providers."""
    return email_service.get_stats()


# Root endpoint
@app.get("/", tags=["Root"])
async def root():
    """Root endpoint with API info."""
    return {
        "service": settings.APP_NAME,
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/health",
        "send_email": "/send-email"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app:app",
        host="0.0.0.0",
        port=8000,
        reload=settings.DEBUG,
        log_level="info"
    )
