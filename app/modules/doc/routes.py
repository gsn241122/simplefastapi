from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from scalar_fastapi import get_scalar_api_reference


router = APIRouter(prefix="/docs", tags=["Documentation"])


# Rapidoc
@router.get("/rapidoc", include_in_schema=False)
async def rapidoc_html():
    return HTMLResponse("""
<html>
<head>
<script src="https://unpkg.com/rapidoc/dist/rapidoc-min.js"></script>
</head>

<body>

<rapi-doc
    spec-url="/openapi.json"
    theme="dark"
    render-style="read"
    show-header="true"
    allow-try="true"
    allow-authentication="true"
    show-method-in-nav-bar="as-colored-block">
</rapi-doc>

</body>
</html>
""")

# Scalar Docs
@router.get("/scalar", include_in_schema=False)
async def scalar_html():
    """
    Menyediakan halamanScalar UI untuk API di module ini.
    """
    return get_scalar_api_reference(
        openapi_url="/openapi.json",
        title="SimpleFastAPI Application API",
        show_sidebar=True
    )