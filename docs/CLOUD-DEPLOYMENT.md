# Hina production API deployment

This package prepares cloud hosting; it does not provision an account, spend money or migrate the existing live backend. The current Vercel frontend continues using the PC runner until a stable API has passed acceptance.

## Configure and launch

1. Select an authorized Linux host with Docker Engine and Compose. Install TLS through a reverse proxy on that host; the API port is bound to loopback.
2. Copy `.env.production.example` to `.env.production` on the host. Enter the production Clerk secret, existing owner ID, exact HTTPS frontend origins, stable public API origin and authorized provider credentials through the host's secret manager or private environment file. Do not paste secrets into chat.
3. Run `docker compose -f compose.production.yaml config --quiet`, then `docker compose -f compose.production.yaml up --build -d`.
4. Check `docker compose -f compose.production.yaml ps`. The image health check uses `/health/live`. Verify anonymous protected requests return 401, the owner can sign in, other accounts cannot access owner operations, document exports work, and realtime connections use the stable API domain.
5. Update the existing frontend API rewrites and rebuild only after that host is healthy. Keep the old backend available during cutover.

The entrypoint rejects development Clerk keys, missing owner IDs, non-HTTPS/wildcard origins, development authentication, disabled persistence and enabled remote machine tools. The API runs as UID 10001 with no extra capabilities. Backend source and dependencies are copied explicitly; the Docker context excludes private environments, database files, runtime logs and memories.

## Storage and recovery

Named volumes preserve the owner's home storage, document assets and cognitive state across restarts. The default SQLite database lives in the home volume. Use one API process with this configuration. For horizontal scaling, use an approved PostgreSQL service and shared/private artifact storage; do not run several independent SQLite copies.

Back up all four volumes and any external database before upgrades. SQLite backups must use SQLite's backup API or a stopped API; do not copy a database during writes. Test restore on a separate host before claiming disaster recovery. Do not run `down --volumes` on the live deployment; it deletes persistent state.

A restart policy does not replace host uptime monitoring, backups or account billing. Cloud hosting also does not grant control over the physical PC. The private desktop controller and vendor image credits remain separate requirements.

## Validation limitations

The startup validator and document pipeline have automated checks. Compose configuration validation passed with `config --no-env-resolution --quiet`. Docker CLI is installed on the development PC, but its Linux engine was not running, so the container image and Compose runtime have not been built or exercised here. Launch on the chosen host and complete the acceptance steps above before switching production traffic.


## HTTPS edge

`compose.tls.yaml` adds a Caddy reverse proxy and persistent certificate volumes. Set `HINAA_API_DOMAIN` and `HINAA_TLS_EMAIL` in the host's private `.env.production`; point that hostname at the provisioned server and allow inbound TCP 80/443. The API retains its loopback host port; Caddy reaches it through the private Compose network. Launch on the host with:

```sh
docker compose --env-file .env.production -f compose.production.yaml -f compose.tls.yaml up -d --build
```

Set the frontend API base and realtime public origin to the new HTTPS API origin only after real health/auth/WebSocket checks pass. Keep the existing live origin until then. Pin the chosen Caddy image digest for the actual production release; the supplied major-version image is a deployment template. DNS, TLS issuance, container build, data durability, and host startup still require verification on a real server. No server has been provisioned during this repair.
