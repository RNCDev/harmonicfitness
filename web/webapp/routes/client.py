"""The built client: its files, and index.html for any other path (the page routes itself). Included last."""
from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, PlainTextResponse

from .. import APP_NAME
from .state import St

router = APIRouter()


@router.get("/{path:path}", include_in_schema=False)
def client(st: St, path: str):
    if path in ("api", "feed") or path.startswith(("api/", "link/", "feed/")):
        raise HTTPException(404, "not found")
    if not st.dist.is_dir():
        if path == "":
            return PlainTextResponse(f"{APP_NAME}'s client isn't built yet: "
                                     "run npm run build in web/client.")
        raise HTTPException(404, "not found")
    root = st.dist.resolve()
    wanted = (root / path).resolve()
    if path and wanted.is_relative_to(root) and wanted.is_file():
        return FileResponse(wanted)
    return FileResponse(root / "index.html", headers={"Cache-Control": "no-cache"})
