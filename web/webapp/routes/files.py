"""The listener's files: the listing, `./harmonicfitness sync`'s three routes, a ZIP import and the export."""
import datetime
from typing import Annotated

import anyio
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field

from .. import folder, store
from .state import POST, St, User, read, tx

router = APIRouter()


class SyncRead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    paths: Annotated[list[Annotated[str, Field(min_length=1, max_length=400)]], Field(max_length=500)]


class SyncChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    path: Annotated[str, Field(min_length=1, max_length=400)]
    base: int | None = None   # the version the computer last saw; None for a file new to the site
    body: str | None = None   # base64; None deletes


class SyncWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")
    changes: Annotated[list[SyncChange], Field(max_length=500)]


def _syncable(path: str) -> bool:
    try:
        store.check_path(path)
    except ValueError:
        return False
    return not folder.skipped(path) and not path.startswith(folder.AUDITIONS) and not folder.local_only(path)


@router.get("/api/sync")
def sync_listing(st: St, uk: User):
    """Every file `./harmonicfitness sync` keeps in step: its path, version and sha256 (the bodies come
    from /api/sync/read, only those the computer lacks). From each file's sealed digest: no body is opened."""
    with read(st) as conn:
        files = store.digests(conn, uk)
    return {"files": [{"path": p, "version": v, "sha256": d} for p, (v, d) in files.items() if _syncable(p)]}


@router.post("/api/sync/read", **POST)
def sync_read(st: St, uk: User, body: SyncRead):
    """The named files' bodies (base64) and versions; a path the site doesn't hold is left out."""
    import base64
    asked = [p for p in dict.fromkeys(body.paths) if _syncable(p)]
    with read(st) as conn:
        files = store.read_many(conn, uk, asked)
    return {"files": [{"path": p, "version": files[p][0], "body": base64.b64encode(files[p][1]).decode("ascii")}
                      for p in asked if p in files]}


@router.post("/api/sync/write", **POST)
def sync_write(st: St, uk: User, body: SyncWrite):
    """Each change applied only over the version the computer last saw (`base`): a file changed on the
    site since is a conflict, left as the site has it. Returns each written path's new version (None:
    deleted), the conflicts, and the paths refused (one the site doesn't keep, or too large)."""
    import base64
    import binascii
    changes, base, refused, total = {}, {}, [], 0
    for c in body.changes:
        if not _syncable(c.path) or c.path in changes:
            refused.append(c.path)
            continue
        if c.body is None:
            data = None
        else:
            try:
                data = base64.b64decode(c.body, validate=True)
            except (binascii.Error, ValueError):
                refused.append(c.path)
                continue
            if len(data) > folder.IMPORT_MAX_FILE:
                refused.append(c.path)
                continue
            total += len(data)
        if total > folder.IMPORT_MAX_TOTAL:
            raise HTTPException(413, f"Over {folder.IMPORT_MAX_TOTAL // 1_000_000} MB in one sync; "
                                     "send it in parts.")
        changes[c.path] = data
        if c.base is not None:
            base[c.path] = c.base
    with tx(st) as conn:
        conflicts = store.write_back(conn, uk, changes, base)
        versions = {p: v for p, v, _ in store.listing(conn, uk)}
    written = {p: versions.get(p) for p in changes if p not in conflicts}
    return {"written": written, "conflicts": sorted(conflicts), "refused": sorted(refused)}


@router.post("/api/import", **POST)
async def import_folder(st: St, uk: User, request: Request):
    """A ZIP of the listener's me/ folder, brought in once: every file kept as it is, over the
    starter files of the same name. Key files, audio, caches, logs and backups are left out."""
    body = await request.body()
    if len(body) > folder.IMPORT_MAX_ZIP:
        raise HTTPException(413, f"That ZIP is over {folder.IMPORT_MAX_ZIP // 1_000_000} MB.")
    try:
        files, left_out = folder.folder_from_zip(body)
    except ValueError as e:
        raise HTTPException(400, str(e)) from None
    if not files:
        raise HTTPException(400, "That ZIP holds none of your folder's files.")

    def save() -> None:
        with tx(st) as conn:
            for path in sorted(files):
                store.put(conn, uk, path, files[path])
    await anyio.to_thread.run_sync(save)
    return {"imported": len(files), "left_out": left_out}


@router.get("/api/export")
def export(st: St, uk: User):
    """Every file of the listener's folder as a ZIP, the same layout as me/ on a computer (unzip it as
    me/ and HarmonicFitness on a computer reads it). Keys are never in it: they aren't files here."""
    import io
    import zipfile
    with read(st) as conn:
        files = store.read_all(conn, uk)
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        for path in sorted(files):
            z.writestr(f"me/{path}", files[path][1])
    day = datetime.date.today().isoformat()
    return Response(buf.getvalue(), media_type="application/zip", headers={
        "Content-Disposition": f'attachment; filename="harmonicfitness-me-{day}.zip"', "Cache-Control": "no-store"})
