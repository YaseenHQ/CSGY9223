"""Telemetry middleware for emitting AWS Embedded Metric Format metrics."""

from time import perf_counter

from aws_embedded_metrics import metric_scope
from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

_NAMESPACE = "OSPSD/HW3"
_SERVICE = "chat_client_service"
_FAILURE_STATUS_CODE = 500


def _endpoint_from_request(request: Request) -> str:
    """Return the FastAPI route template when available."""
    route = request.scope.get("route")
    path = getattr(route, "path", None)
    if isinstance(path, str) and path:
        return path
    return request.url.path


@metric_scope
async def _publish_request_metrics(
    metrics,
    *,
    service: str,
    endpoint: str,
    latency_ms: float,
    status_code: int,
    success: int,
    failure: int,
) -> None:
    """Emit a single EMF event for an HTTP request."""
    metrics.set_namespace(_NAMESPACE)
    metrics.put_dimensions({"Service": service, "Endpoint": endpoint})
    metrics.put_metric("RequestLatency", latency_ms, "Milliseconds")
    metrics.put_metric("SuccessRate", success, "Count")
    metrics.put_metric("FailureRate", failure, "Count")
    await metrics.flush()


class TelemetryMiddleware(BaseHTTPMiddleware):
    """Emit EMF telemetry for every HTTP request."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start = perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            latency_ms = (perf_counter() - start) * 1000
            await _publish_request_metrics(
                service=_SERVICE,
                endpoint=_endpoint_from_request(request),
                latency_ms=latency_ms,
                status_code=_FAILURE_STATUS_CODE,
                success=0,
                failure=1,
            )
            raise

        latency_ms = (perf_counter() - start) * 1000
        is_failure = int(response.status_code >= 400)
        await _publish_request_metrics(
            service=_SERVICE,
            endpoint=_endpoint_from_request(request),
            latency_ms=latency_ms,
            status_code=response.status_code,
            success=1 - is_failure,
            failure=is_failure,
        )
        return response
