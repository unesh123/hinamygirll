# Hina live runner

Open `start-live.bat` to build the authenticated frontend and start the API, preview, public Cloudflare tunnel, and Vercel routing recovery. The verified owner ID stays in the ignored `.runtime/live/owner-id.txt`; Clerk keys stay in existing environment files.

Use `stop.bat` for a graceful stop. To switch from a local development session, stop it first, wait for its services to exit, then start live mode. `start.bat` runs the supervised local development workspace.

The runner checks liveness every 10 seconds, restarts only services it launched, and republishes the existing compiled frontend when a replacement tunnel is healthy. It does not kill unrelated Python, Node, or Cloudflare processes. It refuses public development mode, missing owner authentication, and an occupied API port it does not own.

Public requests require the matching Clerk owner session, including model, memory, upload, and tool routes. Voice and face-tracking sockets require short-lived, single-use identity tickets. Only `/health/live` is public. Machine-changing tools remain local to the computer.

Status: `.runtime/live/runner-state.json`. Diagnostics: `.runtime/live/runner.out.log`, `api.err.log`, `tunnel.err.log`, and `deploy.log`.

The current backend runs on this computer: keep it on, awake, and connected for the public site to work. A permanent hosted backend and production Clerk instance are separate infrastructure changes; the runner cannot keep a powered-off computer online. Existing Clerk development keys are retained.
