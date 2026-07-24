from fastapi import Request, HTTPException, status
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

class RequestMetadata:
    """Container for request metadata"""
    def __init__(self, request: Request):
        self.request = request
        self.client_ip = self._get_client_ip()
        self.user_agent = request.headers.get("user-agent", "Unknown")
        self.method = request.method
        self.path = request.url.path
        self.timestamp = datetime.utcnow()
    
    def _get_client_ip(self) -> str:
        """Extract client IP from request headers"""
        forwarded = self.request.headers.get("X-Forwarded-For")
        if forwarded:
            return forwarded.split(",")[0].strip()
        return self.request.client.host if self.request.client else "Unknown"

async def request_logger(request: Request, call_next):
    """Middleware to log request details"""
    metadata = RequestMetadata(request)
    
    logger.info(f"Incoming request: {metadata.method} {metadata.path} from {metadata.client_ip}")
    logger.debug(f"User-Agent: {metadata.user_agent}")
    
    response = await call_next(request)
    
    logger.info(f"Response status: {response.status_code} for {metadata.method} {metadata.path}")
    
    return response

async def get_request_metadata(request: Request) -> RequestMetadata:
    """Dependency to inject request metadata into endpoints"""
    return RequestMetadata(request)

async def validate_api_key(request: Request):
    """Example dependency to validate API key from headers"""
    api_key = request.headers.get("X-API-Key")
    
    # Skip validation for docs and openapi endpoints
    if request.url.path in ["/docs", "/redoc", "/openapi.json"]:
        return None
    
    if not api_key:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing API Key"
        )
    
    # Here you would validate the API key against your database
    # For now, we just check if it exists
    if len(api_key) < 10:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API Key format"
        )
    
    return api_key
