# Hosted deployment (managed Postgres + stable API origin)

Goal: the live site stops depending on the owner's PC and a Cloudflare quick tunnel.
The API runs on a hosted service, its data lives in managed Postgres, and the web
app (Vercel) reaches it through **one** configurable origin.

## What lives where

| Data | Where on a hosted deploy |
| --- | --- |
| Users, memories, conversations, tasks, reminders, productivity, news/social (SQLAlchemy models) | Postgres (`HINAA_DATABASE_URL`) |
| Autopilot jobs/schedules, goals, security audit + approval tokens, agent task/event journal | Postgres, schema `hinaa_runtime` (same `HINAA_DATABASE_URL`) |
| Phase-10 memory repository (`hinaa_memory.db`: SQLite + FTS5 virtual table/triggers) | **SQLite file** under `HINAA_DATA_DIR` (Render persistent disk). Not in Postgres yet: FTS5 has no drop-in equivalent; porting needs a `tsvector` rewrite. |
| Spoken-topic ledger, run ledger (`run_ledger.db`) | Per-instance SQLite caches/ledgers; safe to lose. |
| Generated media, assets, workspace files | Container filesystem under `/home/hina` (Render disk) |

Local development is unchanged: with no `HINAA_DATABASE_URL` the API uses
`~/.hinaa/hinaa.db` (SQLite) and the standalone store files.

Postgres is selected purely by URL. `postgres://…`, `postgresql://…` and
`postgresql+psycopg://…` are all accepted (normalised to the psycopg v3 driver).
Pool tuning: `HINAA_DB_POOL_SIZE` (5), `HINAA_DB_MAX_OVERFLOW` (10),
`HINAA_DB_POOL_RECYCLE` (1800 s), `HINAA_DB_POOL_TIMEOUT` (30 s).

## Schema migrations

The API applies pending migrations at startup, serialised across instances with a
Postgres advisory lock. No manual step is needed. To run them explicitly (CI, release step, or a
Neon/Supabase database you want to prepare ahead of time):

```bash
cd apps/api
HINAA_DATABASE_URL='postgresql+psycopg://USER:PASS@HOST/DB?sslmode=require' alembic upgrade head
alembic current          # -> 0001_baseline (head)
```

The single baseline revision runs the ordered legacy `MIGRATIONS` list. A database the
API already migrated is *stamped* (`schema_migrations` already lists every version, so
nothing is re-created). New schema changes should be added as new Alembic revisions after
the baseline (`alembic revision -m "..."`).

## Option A — Render Blueprint (API + Postgres)

Accounts: Render (paid: web `starter` for the disk, Postgres `basic-256mb`; the `free`
Postgres plan expires after 30 days), Clerk production instance, GitHub repo connected to Render.

1. Render dashboard → **New → Blueprint** → select this repo/branch. It reads `render.yaml`
   and creates `hinaa-db` (Postgres 16) and `hinaa-api` (Docker).
2. Fill the prompted `sync: false` values: `CLERK_SECRET_KEY` (must be `sk_live_…`),
   `HINAA_ALLOWED_USER_IDS` (your Clerk user id), `CLERK_AUTHORIZED_PARTIES` and
   `HINAA_ALLOWED_ORIGINS` (`https://hinaa-workspace.vercel.app`, comma-separate more),
   and whichever provider keys you use (`GEMINI_API_KEY`, `ANTHROPIC_API_KEY`, …).
   `scripts/start-api-container.py` refuses to boot production without the auth values.
3. Wait for the deploy; `https://<service>.onrender.com/health/live` should return OK
   (this is the configured `healthCheckPath`).
4. Copy your data (below), then switch Vercel (below).

If the container cannot write to the mounted disk (permission denied under
`/home/hina`), the disk is root-owned: set the service's Docker command to start as root
or `chown` the mount in a wrapper entrypoint. I could not verify Render's mount
ownership from this sandbox.

## Option B — Neon or Supabase Postgres + any container host

1. Create the database. Neon: copy the pooled or direct connection string. Supabase: Project
   Settings → Database → connection string (use the **session pooler** or direct string on
   port 5432; the transaction pooler on 6543 does not support session advisory locks).
2. Use it as `HINAA_DATABASE_URL`, with `?sslmode=require` appended
   (`postgresql+psycopg://USER:PASS@HOST/DB?sslmode=require`).
3. Run the API image anywhere (Render/Fly/Railway/VPS) with the same env as step 2 of
   Option A. Optionally run `alembic upgrade head` once beforehand.

## Copy the PC's SQLite data into Postgres

Run on the PC (path of your real DB: default `~/.hinaa/hinaa.db`; stop the local API first):

```bash
cd apps/api
python -m hinaa_api.persistence.copy_sqlite_to_postgres \
  --from sqlite:///C:/Users/<you>/.hinaa/hinaa.db \
  --to 'postgresql+psycopg://USER:PASS@HOST/DB?sslmode=require' \
  --runtime-db apps/api/data/hinaa_agent_tasks.db \
  --runtime-db apps/api/data/hinaa_agent_events.db \
  --runtime-db hinaa_autopilot.db
```

* Creates the schema first, then copies every table; re-running is safe (rows are
  inserted `ON CONFLICT DO NOTHING`, never overwritten).
* Prints `source=… target=…` per table and exits non-zero if any target count is
  short of its source.
* `--runtime-db` is optional and repeatable; use the standalone store files you actually have
  (autopilot/goals/security share `hinaa_autopilot.db` by default). They land in the
  `hinaa_runtime` schema.
* `hinaa_memory.db` is **not** copied (it stays SQLite); upload it to the Render disk at
  `$HINAA_DATA_DIR/hinaa_memory.db` (e.g. via `scp`/`render ssh`) if you want those memories live.

## Switch Vercel to the stable origin

`vercel.json` and `apps/web/vercel.json` keep pointing at the current tunnel so the live site is unchanged
until you cut over. All rewrite destinations are changed from one place:

```bash
node scripts/set-api-origin.mjs --show                               # current origin(s)
node scripts/set-api-origin.mjs https://hinaa-api.onrender.com      # bare https origin
git commit -am "chore(deploy): point Vercel at hosted API" && git push   # Vercel redeploys
```

The script validates the origin (https only, no path/credentials; `http://localhost` allowed
for dev), only touches absolute-URL destinations (the SPA `/index.html` fallback is kept),
and also updates `.vercel/output/config.json` when present. `scripts/live_runner.py` still works
for the tunnel flow: it only rewrites `*.trycloudflare.com` hosts, so once a stable origin is set it
leaves it alone. Stop using `start-live.ps1` after the cut-over.

## Reviewer stack

`docker compose up --build` (repo root `compose.yaml`) starts Postgres 16, the API (dev auth, mock
providers) and the static web build on <http://localhost:8080>.

## Tests and CI

* Default: `pytest` (SQLite).
* Against Postgres: `HINAA_TEST_DATABASE_URL=postgresql+psycopg://… pytest`. Tables are truncated
  between tests; file-path raw-SQL stores are routed to the same database; `:memory:` stores stay on SQLite.
  Two SQLite-specific tests (WAL mode, db-file existence) skip in this mode.
* CI: `.github/workflows/api-postgres.yml` runs the persistence/migration/alembic/copy tests and then the
  full suite against a `postgres:16` service container.

## Raw-SQL stores: what moved

`hinaa_api/persistence/sqlcompat.py` lets the stores that spoke `sqlite3` directly run on Postgres
(placeholders, `AUTOINCREMENT`, `PRAGMA`, `lastrowid`, `REAL`/`BLOB`). A store left at its default location
follows `HINAA_DATABASE_URL`; an explicit file path keeps using SQLite.

* Moved: `autopilot/store.py`, `goals/store.py`, `security/store.py`, `agents/resume.py` (task store),
  `agents/event_log.py`.
* Stayed on SQLite: `memory/repository.py` (FTS5 + triggers, `INSERT OR REPLACE`), `explanation/ledger.py`
  (working-memory cache), `run_ledger.py` (per-machine ledger).
