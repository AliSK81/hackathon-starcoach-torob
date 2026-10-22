# 06 — Deploy (40 / 300 points)

Judging text: "Quality and stability of the deploy process (publishing and running on a server) and final execution in the operational environment." So the judges score two things: a **repeatable, documented deploy** and a **live URL that stays up** during judging, which will most likely happen from Iran.

Stack assumed: FastAPI (Python 3.12) + read-mostly SQLite (~150–400 MB with FTS5) + static frontend, built from a 273 MB CSV that cannot go in Git (GitHub blocks files over 100 MiB).

---

## TL;DR recommendation

1. **Host in Iran** (an Iranian PaaS or an Iranian VPS). Judges in Iran then get low latency, there is no sanctions or account-ban risk, and Docker Hub and PyPI can be reached through local mirrors. International PaaS is a fallback only (see section 2).
2. **Ship one Docker image** with the app and frontend. **Ship the DB separately** as a zstd-compressed, checksummed artifact that is downloaded or copied onto a persistent disk. Open it with `?mode=ro&immutable=1`.
3. Add `/healthz` (process alive) and `/readyz` (DB opened, FTS query works). Add a Docker `HEALTHCHECK`, `restart: unless-stopped`, a `scripts/smoke.sh` run after every deploy, an external uptime monitor (UptimeRobot free), and a GitHub Actions workflow that runs the tests and builds the image.
4. Write `DEPLOY.md` with the exact commands. "Process quality" is part of the score.

---

## 1. Iranian PaaS

Note: most Iranian provider sites timed out or redirected when fetched from outside Iran during this research, likely because of geo-restrictions. Liara's docs loaded. Hamravesh, Arvan and Chabokan details are thinner; see the open questions at the end.

### Liara (لیارا) — best documented, recommended
- **Docker support:** `platform: "docker"` builds your Dockerfile **on Liara's servers** and stores the image in a private Liara registry. It can also deploy a prebuilt image straight from Docker Hub "or any other public registry" (`--image`). Only **one HTTP port** is exposed per app, set with `port`. https://docs.liara.ir/paas/docker/how-tos/deploy-app/ , https://docs.liara.ir/paas/docker/how-tos/deploy-image-from-dockerhub/
- **CLI:** `npm i -g @liara/cli`, then `liara login`, then `liara deploy` from the folder that holds `liara.json`. https://libraries.io/npm/@liara%2Fcli
  ```json
  { "app": "torob-assistant", "platform": "docker", "port": 8000,
    "build": { "cache": true },
    "disks": [{ "name": "data", "mountTo": "/data" }] }
  ```
  One-liner form: `liara deploy --app X --image repo/img:tag --port 8000 --disks data:/data`.
- **Filesystem:** read-only by default. Writes in "writable" mode are lost on restart. **Disks** are the persistent storage: create a disk, mount it to an absolute path, and remove any `VOLUME` from the Dockerfile. Disks support FTP access, backup and restore, and restore via `wget` from the web console shell (`wget -P /data <url>`). That last route is how to put the DB on the disk. https://docs.liara.ir/paas/disks/about/ , https://docs.liara.ir/paas/docker/how-tos/use-disk/ , https://docs.liara.ir/paas/disks/restore-backup-using-wget/
- **Pricing (toman, from liara.ir/pricing):** Earth 0.5 GB / 0.5 vCPU / 5 GB disk = 750,000 per month (1,041 per hour). **Mars 1 GB / 1 vCPU / 10 GB = 1,300,000 per month (1,805 per hour)**. Jupiter 2 GB = 2,300,000 per month. Billing is hourly, so two weeks on Mars costs about 600k toman. No free tier is listed for PaaS. https://liara.ir/pricing/
- **Domain/HTTPS:** each app gets a default subdomain, `<app-id>.liara.run`. Custom domains are added in the panel, and there is a docs page for SSL. https://docs.liara.ir/paas/domains/default-subdomain/ , https://docs.liara.ir/paas/domains/about/
- **Mirrors (useful anywhere in Iran):** Docker Hub mirror `https://docker-mirror.liara.ir` (put it in `daemon.json` → `registry-mirrors`). PyPI mirror `https://package-mirror.liara.ir/repository/pypi/simple`. https://liara.ir/mirrors/docker/ , https://liara.ir/mirrors/pypi/

### Hamravesh / Darkube (هم‌روش / داربک)
- Darkube is Hamravesh's Kubernetes-based PaaS for containers and managed databases. https://hk.linkedin.com/products/hamravesh-darkube-%D8%AF%D8%A7%D8%B1%DA%A9%D9%88%D8%A8
- **CLI and CI:** there is an image at `hamravesh.hamdocker.ir/public/darkube-cli:v1.1` with `darkube build --push -t $IMAGE:$SHA ...` and `darkube deploy --ref <branch> --token $DARKUBE_DEPLOY_TOKEN --app-id $DARKUBE_APP_ID --image-tag $SHA`. https://github.com/AliBigdeli/ReactJS-Hamravesh-Docker-Template/blob/main/.gitlab-ci.yml.sample . A third-party kubectl-like CLI also exists: https://github.com/rahacloud/darkubectl
- Hamravesh runs a Docker Hub mirror, `hub.hamdocker.ir` (listed in https://github.com/MiravaOrg/Mirava).
- Pricing, free tier and volume details could not be fetched (hamravesh.com timed out).

### ArvanCloud Cloud Container (ابرآروان)
- This is Kubernetes (OpenShift-like) PaaS. You can deploy from a git repo (`arvan paas new-app`), from a container image (public or private registry, chosen in the panel), or with kubectl and a downloaded kubeconfig. CLI: `arvan login` (with an API key from the panel), then `arvan paas ...`. https://docs.arvancloud.ir/en/cloud-container/create-app/ , https://docs.arvancloud.ir/en/cloud-container/create-app/container-image , https://docs.arvancloud.ir/en/developer-tools/cli/
- A community workflow updates the image with `arvan paas set image deployment <app> <container>=<img:tag>` from GitHub Actions. https://arash-hatami.ir/arvancloud-paas-action/ . Example manifests: https://github.com/arvancloud/paas-examples
- Docker mirror: `docker.arvancloud.ir`. Arvan's CDN can also front any origin with TLS.
- Pricing, free tier and PVC sizes were not retrieved (the site redirect-looped).

### Chabokan (چابکان)
- Generic multi-language PaaS (https://ful.io/technology/PaaS/Chabokan). It also runs mirrors at `iran.chabokan.net`. Docker-specific docs, pricing and CLI details could not be retrieved (timeout).

### Sanctions and mirrors (important for any Iran-hosted build)
- **Docker Hub returns 403 to Iranian IPs.** Docker's error page lists Iran among blocked regions for export control. https://forums.docker.com/t/docker-hub-is-not-accessible-from-russia/141678 . Configure a mirror on any Iranian VPS or builder: `docker-mirror.liara.ir`, `docker.arvancloud.ir`, `hub.hamdocker.ir`, `docker-mirror.kargadan.ir`, and others. Curated list: https://github.com/MiravaOrg/Mirava . Toolkit: https://github.com/aminrpg/iranian-servers-toolkit . Community reports say namespaced (non-official) images sometimes fail through mirrors, so prefer official images like `python:3.12-slim` and `caddy:2`.
- **`COPY --from=ghcr.io/astral-sh/uv`** pulls from ghcr.io, which may not be reachable from Iran (unverified). Safer: `pip install uv` from a PyPI mirror, or plain pip.
- **PyPI mirrors** (set `PIP_INDEX_URL`, or `UV_DEFAULT_INDEX` for uv):
  - Liara: `https://package-mirror.liara.ir/repository/pypi/simple`
  - Runflare: `https://mirror-pypi.runflare.com/simple` (https://runflare.com/mirrors/pypi-mirror/)
  - Kargadan: `https://mirror.kargadan.ir/repository/pypi-group/simple/` (https://mirror.kargadan.ir/)
  - NovinCloud, ITO, Ferdowsi: see https://raw.githubusercontent.com/mani1728/pypi-mirror-tournament/main/config/mirrors.conf
- Make the index a **build arg** so the same Dockerfile works inside and outside Iran:
  `ARG PIP_INDEX_URL=https://pypi.org/simple` → `ENV PIP_INDEX_URL=$PIP_INDEX_URL`.

---

## 2. International PaaS (fallback only)

| Platform | Free tier (Oct 2026) | Disk | Notes |
|---|---|---|---|
| **Fly.io** | **No free tier** for new orgs. The trial ends after 2 h of machine runtime or 7 days. shared-cpu-1x with 1 GB costs about $6.70/mo. | Volumes $0.15/GB-mo | Needs a card. https://docs.fly.io/about/pricing |
| **Render** | Free web service, spins down after 15 min idle, ~1 min cold start, 750 h/mo | **No persistent disk on free.** The filesystem is ephemeral. | A cold start in front of judges is bad. https://render.com/docs/free |
| **Railway** | Trial: one-time $5 credit (1 GB RAM, 0.5 GB volume). Free plan: $1/mo credit, 0.5 GB RAM. Hobby: $5/mo, 5 GB volume. | 0.5 GB volume on trial/free, too small for the DB | https://docs.railway.com/reference/pricing/plans |
| **HF Spaces (Docker)** | **Docker and Gradio Spaces now require a paid plan (PRO) to create.** CPU Basic is 2 vCPU / 16 GB / 50 GB disk, not persistent, and sleeps when unused. | Ephemeral | https://huggingface.co/docs/hub/spaces-overview |

**Accessibility from Iran:** all four are US companies bound by OFAC. Signing up with an Iranian identity, IP or card is not viable, and accounts can be suspended. Precedent: GitHub, AWS, DigitalOcean and SoftLayer all blocked Iranian users (https://www.computing.co.uk/news/3079708/github-blocks-developers , https://iranhumanrights.org/2019/08/more-iranians-forced-to-rely-on-unsafe-online-hosting-after-amazon/). Their `*.fly.dev`, `*.onrender.com` and `*.hf.space` domains may also be slow or filtered for judges in Iran (unverified). Use them only if the team is outside Iran and the judges are known to reach them.

---

## 3. Plain VPS: Docker Compose + Caddy

A 1–2 GB RAM Iranian VPS is enough. Set `registry-mirrors` in `/etc/docker/daemon.json` first.

`docker-compose.yml`:
```yaml
services:
  app:
    image: torob-assistant:${TAG:-latest}
    build: { context: ., args: { PIP_INDEX_URL: "${PIP_INDEX_URL:-https://pypi.org/simple}" } }
    restart: unless-stopped
    environment: [DB_PATH=/data/app.db, LOG_LEVEL=info]
    volumes: ["./data:/data:ro"]          # DB copied here once; read-only mount
    expose: ["8000"]
    healthcheck:
      test: ["CMD", "python", "-c", "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/readyz',timeout=3).status==200 else 1)"]
      interval: 15s
      timeout: 5s
      retries: 3
      start_period: 30s
    mem_limit: 900m
    logging: { driver: json-file, options: { max-size: "10m", max-file: "3" } }
  caddy:
    image: caddy:2
    restart: unless-stopped
    ports: ["80:80", "443:443"]
    volumes: ["./Caddyfile:/etc/caddy/Caddyfile:ro", "caddy_data:/data", "caddy_config:/config"]
    depends_on: { app: { condition: service_healthy } }
volumes: { caddy_data: {}, caddy_config: {} }
```

`Caddyfile`:
```
shop.example.ir {
    encode zstd gzip
    reverse_proxy app:8000 {
        lb_try_duration 30s        # hold and retry requests while app restarts → near-zero-downtime
        health_uri /healthz
    }
}
```

- **Automatic HTTPS** needs DNS A/AAAA records pointing at the VPS, ports 80 and 443 reachable, and a persistent `/data` volume. Caddy uses Let's Encrypt and falls back to ZeroSSL. For a raw IP it serves a self-signed internal CA, which browsers will warn about. https://caddyserver.com/docs/automatic-https
- **Let's Encrypt and Iran:** LE subscriber agreement v1.7 (4 June 2026) added a "comprehensive U.S. sanctions" warranty in §3.1 (https://letsencrypt.org/documents/LE-SA-v1.7-June-04-2026.pdf , https://linuxiac.com/lets-encrypt-certificate-rules-now-include-u-s-sanctions-warranties/). v1.8 replaced it with a generic compliance-with-laws section and states it "does not change where or to whom" LE issues (https://community.letsencrypt.org/t/updating-the-let-s-encrypt-subscriber-agreement-to-v1-8/248355). Historically LE issued to `.ir` domains and Iranian IPs, blocking only some government domains (https://community.letsencrypt.org/t/letsencrypt-org-not-accessible-from-iran/156871). Practically, ACME issuance from an Iranian VPS usually works but carries some risk. Fallbacks: the PaaS's own TLS subdomain, or ArvanCloud CDN in front with its TLS.
- **Redeploy, near zero downtime:**
  ```bash
  git pull && docker compose build app && docker compose up -d --no-deps --wait app && ./scripts/smoke.sh https://shop.example.ir
  ```
  `--wait` blocks until the app is healthy. Caddy's `lb_try_duration` absorbs the few seconds of restart. Roll back with `TAG=<prev> docker compose up -d --no-deps app`. Always tag images with the git SHA.
- If image builds on the VPS are slow, build in GitHub Actions, then `docker save | zstd` and `scp` the image to the VPS and `docker load`. This also avoids needing a registry reachable from Iran.

---

## 4. Shipping the data

| Option | Pros | Cons |
|---|---|---|
| **A. Build DB during `docker build`** (CSV fetched via `ADD`/`curl` in a builder stage, `python build_db.py`, then copy only `app.db`) | One self-contained image, reproducible, no runtime downloads | Image grows by 150–400 MB. Slow builds. The CSV URL must be reachable from the builder (Liara builds on its own servers). Upload or push size limits are unknown. |
| **B. Build at container startup** | Small image | Slow cold start (minutes), RAM spike during FTS build, and a crash loop if it fails. **Avoid.** |
| **C. Prebuilt DB artifact → persistent disk** (recommended) | Fast, and decoupled from code deploys (redeploying code doesn't touch data). Checksum makes it verifiable. | One extra one-time step per environment |

**Recommended flow (C):**
1. `python scripts/build_db.py data/*.csv -o app.db` locally or in CI. Then `VACUUM; ANALYZE; PRAGMA optimize;` and FTS5 `INSERT INTO fts(fts) VALUES('optimize')`.
2. `zstd -19 --long=27 -T0 app.db -o app.db.zst && sha256sum app.db app.db.zst > SHA256SUMS`
3. Publish it:
   - **GitHub Release asset.** The limit is **< 2 GiB per file, up to 1000 assets per release** (https://docs.github.com/en/repositories/releasing-projects-on-github/about-releases). `gh release create data-v1 app.db.zst SHA256SUMS`. Release download from Iran may be slow or flaky; a proxy like `gitdl.theazizi.ir` is listed in Mirava (unverified).
   - Mirror it to an Iranian object store (Liara Object Storage, Arvan S3) for the Iranian server.
4. **Entrypoint:** if `/data/app.db` is missing or its sha256 differs from the pinned `DB_SHA256`, download to `/data/app.db.tmp`, verify, `zstd -d`, then atomically `mv` it into place. Then start uvicorn. On Liara the alternative is a one-time `wget` and `zstd -d` from the console shell into the mounted disk. On a VPS it is a one-time `scp`.
5. Keep a **build-time fallback**: `ARG BAKE_DB=0`, and when it is 1, `COPY app.db /data/app.db`. This gives a single fully self-contained image for an emergency `docker save` handoff.

**Git LFS: don't use it.** GitHub Free allows 2 GB max per file but only **10 GiB storage and 10 GiB/month bandwidth**. Once bandwidth runs out, LFS is disabled until next month, so every clone or CI run eats into the quota. https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-git-large-file-storage , https://docs.github.com/en/billing/concepts/product-billing/git-lfs . Files over 100 MiB are blocked and over 50 MiB warn: https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github

**Compression:** text-heavy SQLite with FTS indexes typically compresses about 3–5x with zstd. This is an estimate; measure on the real DB. Use `zstd -19 --long` for the artifact. gzip is usually 20–30% larger and much slower to decompress. Alternatively ship the CSV compressed (also roughly 4–6x for CSV) and build the DB in CI.

---

## 5. Dockerfile and runtime

```dockerfile
# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS builder
ARG PIP_INDEX_URL=https://pypi.org/simple
ENV PIP_INDEX_URL=$PIP_INDEX_URL PIP_DISABLE_PIP_VERSION_CHECK=1 UV_DEFAULT_INDEX=$PIP_INDEX_URL \
    UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=0
RUN pip install uv              # avoids ghcr.io (COPY --from=ghcr.io/astral-sh/uv) which may be unreachable from Iran
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev --no-install-project
COPY . .
RUN --mount=type=cache,target=/root/.cache/uv uv sync --frozen --no-dev

FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends zstd && rm -rf /var/lib/apt/lists/* \
 && useradd -r -u 10001 app && mkdir /data && chown app /data
WORKDIR /app
COPY --from=builder --chown=app /app /app
ENV PATH=/app/.venv/bin:$PATH PYTHONUNBUFFERED=1 DB_PATH=/data/app.db
USER app
EXPOSE 8000
HEALTHCHECK --interval=15s --timeout=5s --start-period=30s --retries=3 \
  CMD python -c "import urllib.request,sys;sys.exit(urllib.request.urlopen('http://127.0.0.1:8000/healthz',timeout=3).status!=200)"
CMD ["sh","-c","./scripts/entrypoint.sh && exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers ${WEB_CONCURRENCY:-2} --proxy-headers --forwarded-allow-ips='*'"]
```
The uv pattern follows https://docs.astral.sh/uv/guides/integration/docker/ (multi-stage, cache mounts, `UV_COMPILE_BYTECODE`, `UV_LINK_MODE=copy`). Add `.venv`, `data/`, `*.csv` and `*.db` to `.dockerignore` so the 273 MB CSV is never sent as build context. Also add them to `.liaraignore` if Liara uploads the folder. If the team uses plain pip, `pip install --no-cache-dir -r requirements.txt` in the same layout is fine. Debian apt inside the build also needs an Iranian mirror (Liara has Debian and Ubuntu mirrors), or skip `zstd` and decompress with Python `zstandard`.

**SQLite read-only concurrency:**
- The catalog DB is never written at runtime, so open it as `sqlite3.connect("file:/data/app.db?mode=ro&immutable=1", uri=True, check_same_thread=False)`. `immutable=1` skips **all locking and change detection**. That is the fastest option, but you must never swap the file while it is open: restart the app after replacing the DB. https://www.sqlite.org/uri.html
- Use one connection per worker thread or per request; they are cheap. Run `PRAGMA mmap_size=536870912` and `PRAGMA cache_size=-65536` per connection. With mmap the OS page cache is **shared across uvicorn workers**, so 2 workers do not double the DB memory.
- WAL only matters if you write. Put user state (follow-ups, saved lists) in a **separate small writable DB** on the persistent disk with `PRAGMA journal_mode=WAL; busy_timeout=5000`, or keep it client-side (localStorage) to stay stateless.
- **Workers:** 1 GB plan → `--workers 2`. Each Python worker with FastAPI plus deps is roughly 60–120 MB RSS. Add the LLM client libraries if used.
- FastAPI `def` (sync) endpoints run in a threadpool, so blocking sqlite calls are fine there. Don't call sqlite inside `async def` without `run_in_threadpool`.
- Serve the static frontend with `StaticFiles` from FastAPI (one container), or from Caddy `file_server` on a VPS. Use hashed filenames with long cache times.

---

## 6. Stability and observability

- **Endpoints:** `/healthz` returns 200 with no dependencies (liveness). `/readyz` runs `SELECT count(*) FROM products LIMIT 1` plus one FTS `MATCH` and returns `{db_sha, rows, version: GIT_SHA, uptime}`. Use it for Docker or Caddy health checks and for display in the demo video.
- **Structured logs:** JSON to stdout (e.g., `structlog` or `python-json-logger`) with request id, path, status and latency in ms. The PaaS or Docker collects stdout. Configure log rotation (compose `max-size`).
- **Uptime monitoring:**
  - UptimeRobot free: 50 monitors, 5-min interval, 1 status page ("hobby and non-profit"). https://uptimerobot.com/pricing/
  - Better Stack free: 10 monitors and heartbeats, 1 status page, Slack and email alerts. https://betterstack.com/pricing
  - Both are probing from abroad, so an Iran-only-reachable host may look "down" to them (unverified). Add a tiny cron `curl` from an Iranian box as backup.
- **Smoke test** (`scripts/smoke.sh BASE_URL`, exit non-zero on failure, run after every deploy and in CI against the built container):
  ```bash
  set -euo pipefail; B=${1:-http://localhost:8000}
  curl -fsS "$B/healthz" >/dev/null
  curl -fsS "$B/readyz" | grep -q '"rows"'
  curl -fsS -G "$B/api/search" --data-urlencode "q=گوشی سامسونگ" | grep -q '"results"'
  curl -fsS "$B/" | grep -qi '<html'
  echo "SMOKE OK $B"
  ```
- **GitHub Actions CI** (`.github/workflows/ci.yml`): on every push, set up Python, `uv sync`, `pytest` against a **small fixture DB** built from a 1–2k-row CSV sample committed to the repo. Then `docker build`, `docker run -d -p 8000:8000 -v fixture:/data`, and `scripts/smoke.sh`. On tag `v*`, also push the image to GHCR and/or `docker save | zstd` as a release asset. Optional deploy job: `liara deploy --api-token ${{ secrets.LIARA_TOKEN }} ...` (Liara CLI supports token auth, flag name unverified), the `darkube deploy ...` token flow, or `ssh vps 'cd app && ./deploy.sh'`. Note that GitHub-hosted runners are in the US. Pushing to an Iranian registry or SSH-ing into an Iranian VPS from them can fail if the Iranian side filters foreign IPs, so manual deploy from a laptop in Iran is an acceptable fallback (document it).
- **Freeze before judging:** pin image tag and DB sha, disable auto-deploy, keep the previous image for one-command rollback, and check the URL from an Iranian mobile network (MCI or Irancell) as well as from fixed broadband.

---

## Unverified / open questions
- **Liara:** max upload size for `liara deploy` (source upload) and whether a ~400 MB image layer is OK; whether plan disk quota covers "disks"; free credit for new accounts; zero-downtime or healthcheck settings; exact CLI token flag for CI; whether builds can reach the Torob dataset URL and GitHub Releases.
- **Hamravesh/Darkube, ArvanCloud Cloud Container, Chabokan:** current pricing for about 1 GB RAM, free tiers, persistent volume sizes, and HTTPS on default subdomains. Their sites were unreachable from the research environment.
- Whether **ghcr.io** and **GitHub Releases downloads** are reliably reachable from Iranian datacenters (they are reportedly throttled at times).
- Whether `*.onrender.com`, `*.fly.dev` and `*.hf.space` are reachable without VPN on Iranian ISPs today.
- Actual zstd and gzip ratios for our SQLite and FTS DB, and real RSS per uvicorn worker. Measure once the DB exists.
- Whether Let's Encrypt issuance from an Iranian VPS works in practice under SA v1.8, and how Caddy behaves if ACME fails (it retries with backoff; the site has no valid cert meanwhile).
- Whether UptimeRobot and Better Stack probes can reach Iran-hosted endpoints.
- The judges' environment: do they test from inside Iran, with or without VPN? Ask the organizers. This decides Iran-hosted versus international hosting.
