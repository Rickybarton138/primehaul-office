"""
Error tracking middleware for PrimeHaul Office Manager.
Logs 5xx errors to the database.
"""

import traceback
import logging
from datetime import datetime
from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from app.database import SessionLocal

logger = logging.getLogger(__name__)


class ErrorTrackingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        try:
            response = await call_next(request)
            if response.status_code >= 500:
                self._log_error(
                    request=request,
                    status_code=response.status_code,
                    error_message=f"HTTP {response.status_code}",
                    level="ERROR",
                )
            return response
        except Exception as e:
            self._log_error(
                request=request,
                status_code=500,
                error_message=str(e),
                traceback_str=traceback.format_exc(),
                level="CRITICAL",
            )
            raise

    def _log_error(
        self,
        request: Request,
        status_code: int,
        error_message: str,
        traceback_str: str = "",
        level: str = "ERROR",
    ):
        try:
            from app.models import ErrorLog

            db = SessionLocal()
            try:
                error = ErrorLog(
                    level=level,
                    source=f"{request.method} {request.url.path}",
                    message=error_message[:2000],
                    traceback=traceback_str[:5000] if traceback_str else None,
                    request_method=request.method,
                    request_path=str(request.url.path),
                    request_ip=request.client.host if request.client else None,
                    status_code=status_code,
                    created_at=datetime.utcnow(),
                )
                db.add(error)
                db.commit()
            finally:
                db.close()
        except Exception as log_err:
            logger.error(f"Failed to log error to DB: {log_err}")
