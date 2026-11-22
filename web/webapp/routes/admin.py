"""The admin screen's one route (0.87.0): the site's books for a range of days. Only an account HARMONICFITNESS_ADMINS
names gets an answer; anyone else gets 404, signed in or not."""
import anyio
from fastapi import APIRouter, HTTPException

from .. import books, fly
from .state import Admin, St, read

router = APIRouter()


@router.get("/api/admin/books")
async def get_books(st: St, uk: Admin, days: int = 30):
    if days not in books.WINDOWS:
        raise HTTPException(400, f"days must be one of {', '.join(str(d) for d in books.WINDOWS)}")

    def work() -> dict:
        est = fly.estimate(st.settings.fly_token, st.settings.fly_app)
        with read(st) as conn:
            return books.summary(conn, days, est)
    return await anyio.to_thread.run_sync(work)
