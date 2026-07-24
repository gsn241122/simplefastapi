from pydantic import BaseModel, Field
from typing import Any, Optional, Generic, TypeVar, List, Union
from datetime import datetime

T = TypeVar("T")

class APIResponse(BaseModel, Generic[T]):
    """Standard response wrapper for all API endpoints"""
    success: bool = Field(default=True, description="Indicates if the request was successful")
    message: str = Field(default="Operation completed successfully", description="Human-readable message")
    data: Optional[Union[T, List[T]]] = Field(default=None, description="Response data payload")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Response timestamp")
    error: Optional[str] = Field(default=None, description="Error message if success is False")

    class Config:
        from_attributes = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }

class StandardJSONResponse:
    """Custom response class to automatically wrap responses"""
    
    @staticmethod
    def success(data: Any = None, message: str = "Operation completed successfully"):
        return APIResponse(
            success=True,
            message=message,
            data=data
        )
    
    @staticmethod
    def error(message: str, status_code: int = 400):
        return APIResponse(
            success=False,
            message=message,
            error=message
        ), status_code
