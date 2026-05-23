# Deploy — Production Runbook

> Đọc khi cần. Hiện tại **chỉ owner có SSH** vào server prod; dev senior
> sẽ được cấp sau probation.

## 1. Access policy

| Role | Có quyền gì |
|---|---|
| Owner (**Nguyên** — `letannguyen210496@gmail.com`) | SSH root + sudo, deploy, secret rotation, certbot |
| Senior dev (sau probation 1-3 tháng) | SSH read-only logs + `docker compose logs/ps`; deploy via PR auto-merge khi setup CI |
| Junior dev | Chỉ qua PR; không SSH |
| External | Không |

Xin SSH access: ping **Nguyên**, gửi public key (ed25519 ≥ 256-bit), kèm commit/PR ID đầu tiên đã merge.

## 2. Server info

| | Value |
|---|---|
| Hostname | `letannguyen` |
| OS | Linux (Debian-family per nginx config layout) |
| Working dir | `/var/www/ai-translation` |
| Web entry | `https://translate.aicorelabs.click` (mới setup) |
| Other apps trên cùng host | `aicoresolution-backend-prod:7080`, `aicoresolution-db-prod:5432` |
| nginx version | apt-managed (Debian package) |
| Cert manager | Certbot (letsencrypt) |
| Docker | Docker Engine + docker compose v2 plugin |

Ports đã dùng (đừng đụng):
```
7080  aicoresolution backend
5432  aicoresolution db
8084  unknown (proxy via /api/ trong default nginx site)
8090  myfilethrow.click Node app
443   nginx HTTPS
80    nginx HTTP redirect
```

Ports ai-translation chiếm (bound 127.0.0.1):
```
7100  Next.js prod (container :3000)
7101  FastAPI prod  (container :8000)
7102  PostgreSQL    (container :5432)
7103  Redis         (container :6379)
```

## 3. First deploy (one-time)

```bash
ssh root@<server>
cd /var/www/

# 1. Clone
git clone <repo-url> ai-translation
cd ai-translation

# 2. Configure
cp .env.example .env
nano .env
# Tối thiểu:
#   DASHSCOPE_API_KEY=sk-<prod key, NOT dev key>
#   CORS_ALLOWED_ORIGINS=https://translate.aicorelabs.click
#   POSTGRES_PASSWORD=<random 32-char>
# Không đổi DATABASE_URL / REDIS_URL — internal docker hostnames.

# 3. Build + start
docker compose -f docker-compose.prod.yml up -d --build
# Lần đầu ~10-15 phút (PaddleOCR bake ~1GB).

# 4. Migrate DB
docker compose -f docker-compose.prod.yml exec api alembic upgrade head

# 5. Verify containers healthy
docker compose -f docker-compose.prod.yml ps
# Tất cả phải "healthy" (api, postgres, redis).

# 6. Direct backend probe
curl -i http://127.0.0.1:7101/health   # → 200 {"status":"ok"}

# 7. nginx site
ln -s /var/www/ai-translation/deploy/nginx/ai-translation.conf \
      /etc/nginx/sites-available/ai-translation
ln -s /etc/nginx/sites-available/ai-translation \
      /etc/nginx/sites-enabled/
nginx -t && systemctl reload nginx

# 8. DNS — registrar: A record translate.aicorelabs.click → server IP
dig +short translate.aicorelabs.click   # confirm propagation

# 9. SSL — Certbot edits the nginx file in-place to add HTTPS block + redirect
certbot --nginx -d translate.aicorelabs.click

# 10. End-to-end smoke
curl -I https://translate.aicorelabs.click           # → 200 from Next.js
curl -s https://translate.aicorelabs.click/api/health
# Mở browser, upload sample DOCX, verify download.
```

## 4. Update deploy (subsequent)

```bash
ssh root@<server>
cd /var/www/ai-translation

# 1. Pull latest main
git status              # confirm clean tree
git pull origin main

# 2. Rebuild + restart changed services
docker compose -f docker-compose.prod.yml up -d --build

# 3. Migrate (nếu PR có Alembic revision mới)
docker compose -f docker-compose.prod.yml exec api alembic upgrade head

# 4. Verify
docker compose -f docker-compose.prod.yml ps
curl -s https://translate.aicorelabs.click/api/health
```

Tip: chỉ rebuild service đổi:
```bash
docker compose -f docker-compose.prod.yml up -d --build api worker
# (web không đổi → bỏ qua)
```

## 5. Common ops scenarios

### Frontend-only update (no API change)

```bash
docker compose -f docker-compose.prod.yml up -d --build web
```

### Backend code update (no DB schema change)

```bash
docker compose -f docker-compose.prod.yml up -d --build api worker
```

### DB schema change (Alembic revision merged)

```bash
docker compose -f docker-compose.prod.yml up -d --build api
docker compose -f docker-compose.prod.yml exec api alembic upgrade head
docker compose -f docker-compose.prod.yml restart worker
```

### Add new env var

1. Edit `/var/www/ai-translation/.env` trên server (KHÔNG commit).
2. `docker compose -f docker-compose.prod.yml restart api worker`.
3. Update `.env.example` trong repo, commit, push.

### Rotate DashScope API key

1. Tạo key mới trên dashscope-intl portal.
2. Edit `.env`: `DASHSCOPE_API_KEY=<new key>`.
3. `docker compose -f docker-compose.prod.yml restart api worker`.
4. Test 1 translation.
5. Sau 24h confirm OK → revoke key cũ trên portal.

### Rotate Postgres password

1. `docker compose exec postgres psql -U postgres -c "ALTER USER postgres PASSWORD '<new>';"`
2. Update `.env`: `POSTGRES_PASSWORD=<new>` + `DATABASE_URL=postgresql+asyncpg://postgres:<new>@postgres:5432/aitranslation`
3. `docker compose -f docker-compose.prod.yml restart api worker`

## 6. Logs

### Docker logs

```bash
# Live tail tất cả
docker compose -f docker-compose.prod.yml logs -f --tail=100

# 1 service
docker compose -f docker-compose.prod.yml logs -f --tail=200 api
docker compose -f docker-compose.prod.yml logs -f --tail=200 worker

# Filter errors
docker compose -f docker-compose.prod.yml logs api 2>&1 | grep -iE "error|exception|traceback"
```

### nginx logs

```bash
sudo tail -100 /var/log/nginx/access.log
sudo tail -50  /var/log/nginx/error.log
# Hoặc filter cho subdomain:
sudo grep "translate.aicorelabs.click" /var/log/nginx/access.log | tail -50
```

### Disk usage check

```bash
df -h                                    # overall
du -sh /var/www/ai-translation/.data/    # uploaded jobs (có thể to)
docker system df                         # docker images/containers/volumes
```

Cleanup .data nếu quá to:
```bash
# CAREFUL — xóa files của jobs > 30 ngày
find /var/www/ai-translation/.data/jobs -mtime +30 -type d -exec rm -rf {} +
```

## 7. Rollback

### Rollback code (không DB schema change)

```bash
cd /var/www/ai-translation
git log --oneline -10
git reset --hard <previous-commit-sha>     # ⚠️ destructive
docker compose -f docker-compose.prod.yml up -d --build
```

⚠️ Hỏi owner trước nếu `git status` không clean — có thể là in-flight hotfix.

### Rollback DB schema (Alembic)

```bash
docker compose -f docker-compose.prod.yml exec api alembic downgrade -1
# Hoặc về revision cụ thể:
docker compose -f docker-compose.prod.yml exec api alembic downgrade <rev_id>
```

⚠️ Downgrade chỉ an toàn nếu revision có `downgrade()` function viết đúng. Alembic autogen không phải lúc nào cũng correct cho complex changes.

### Total reset (nuclear option)

```bash
cd /var/www/ai-translation
docker compose -f docker-compose.prod.yml down -v   # ⚠️ -v xoá volume = mất data
git reset --hard <good-commit>
docker compose -f docker-compose.prod.yml up -d --build
docker compose -f docker-compose.prod.yml exec api alembic upgrade head
# .env preserved (gitignored)
# .data/ preserved (bind mount, không trong named volume)
```

Trừ khi crisis, không nuke.

## 8. Backup

Hiện chưa có automated backup. Manual:

```bash
# DB dump
docker compose -f docker-compose.prod.yml exec postgres \
  pg_dump -U postgres aitranslation > /backup/aitranslation-$(date +%F).sql

# .data/ tarball (uploaded + output files)
tar czf /backup/data-$(date +%F).tar.gz \
  -C /var/www/ai-translation .data/

# Scp về máy local định kỳ
scp root@<server>:/backup/aitranslation-*.sql ~/backups/
```

TODO: cron job + offsite storage nếu PoC chuyển production thật.

## 9. Monitoring (basic)

Không có Prometheus / Grafana setup. Basic checks:

```bash
# Sysadmin one-liner — chạy daily
echo "=== Containers ===" && docker compose -f docker-compose.prod.yml ps && \
echo "=== Disk ===" && df -h / && \
echo "=== Health ===" && curl -sf https://translate.aicorelabs.click/api/health && \
echo "=== Recent errors (last 24h) ===" && \
  docker compose -f docker-compose.prod.yml logs --since 24h api 2>&1 | grep -ciE "error|exception"
```

Optional setup uptime-kuma / healthchecks.io trỏ về `/api/health` để alert qua Slack/email.

## 10. Common deploy failures + fixes

| Symptom | Cause | Fix |
|---|---|---|
| `pull access denied for ai-translation-backend` | Compose race trying to pull non-existent image | Đã fix trong `docker-compose.prod.yml` (worker có `build:` + `pull_policy: never`). Re-pull repo, re-up. |
| `COPY /frontend/public failed` | Dir không tồn tại | Đã fix (`frontend/public/.gitkeep` committed). Re-pull. |
| 500 từ `/api/jobs` nhưng `/api/health` OK | Alembic chưa chạy → tables missing | `docker compose exec api alembic upgrade head` |
| CORS error trên prod | `CORS_ALLOWED_ORIGINS` thiếu prod origin | Add `https://translate.aicorelabs.click` vào `.env`, restart api |
| 502 từ nginx | Backend container down | `docker compose ps`; nếu unhealthy → `docker compose logs api` để debug |
| SSE stream hangs | nginx buffering on | Confirm `deploy/nginx/ai-translation.conf` có `proxy_buffering off` trong `/api/` block |
| Certbot renew fail | DNS thay đổi / port 80 block | `certbot certificates`, `certbot renew --dry-run` |
| Disk full | `.data/` jobs accumulated | Section 6 cleanup |

## 11. Architecture in prod

```
Internet
   │ HTTPS
   ▼
nginx :443
   │
   ├─ /api/  → 127.0.0.1:7101 (FastAPI in docker)
   └─ /      → 127.0.0.1:7100 (Next.js in docker)

docker network "ai-translation_default":
   api ─── postgres :5432
       └── redis    :6379
   worker (no port; reads from redis queue)
   postgres (volume: pgdata)
   redis    (volume: redisdata)
```

nginx terminates SSL. Containers all bind 127.0.0.1 — không expose ra Internet trực tiếp.

## Where else to look

- Compose file: `docker-compose.prod.yml`
- nginx site: `deploy/nginx/ai-translation.conf`
- Backend Dockerfile: `backend/Dockerfile`
- Frontend prod Dockerfile: `frontend/Dockerfile.frontend.prod`
- Health endpoint: `backend/src/app/api/routes/health.py`
- Current prod state: `docs/STATE.md` section "Production deployment"
