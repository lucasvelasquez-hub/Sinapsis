"""La suite nunca corre contra Supabase, aunque `DATABASE_URL` (backend/.env) apunte allí."""

from app.core.database import engine

LOCAL_HOSTS = {"localhost", "127.0.0.1"}


def test_suite_runs_against_local_db() -> None:
    assert engine.url.host in LOCAL_HOSTS
