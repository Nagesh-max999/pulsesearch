from fastapi import APIRouter, Response

from app.core.metrics import metrics_response

router = APIRouter(tags=["metrics"])


@router.get("/metrics")
async def metrics() -> Response:
    body, content_type = metrics_response()
    return Response(content=body, media_type=content_type)
