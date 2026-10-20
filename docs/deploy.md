# Deploy Lifunze ke VPS Sirius

Pola mengikuti Rephore & SpellWar: repo di `/opt/sirius/projects/lifunze`,
container hanya di jaringan Docker internal, publik lewat **sirius-caddy**
yang sudah ada. Tidak ada port container yang dipublish ke publik.

## Struktur di VPS

- Repo: `/opt/sirius/projects/lifunze` (clone dari GitHub `qualzecoat/Lifunze`)
- Override compose + env: `/opt/sirius/compose/lifunze/`
  - `docker-compose.sirius.yml` — menempelkan container ke network caddy + tanpa ports
  - `secrets.env` (chmod 600) — semua nilai dari `.env.example` versi production
- Backup: `/home/sirius/lifunze-backup/` (cron harian 03:00, retensi 7 hari)

## Langkah deploy pertama

```bash
# 1. Di VPS: clone & siapkan env
cd /opt/sirius/projects && git clone https://github.com/qualzecoat/Lifunze.git lifunze
mkdir -p /opt/sirius/compose/lifunze
cp /opt/sirius/projects/lifunze/scripts/backup-db.sh /opt/sirius/compose/lifunze/
# tulis secrets.env dari .env.example (isi rahasia hasil generate), chmod 600

# 2. Override Sirius (sekali saja): service db/api/web menempel network
#    eksternal milik sirius-caddy; tanpa blok ini Caddy tidak bisa menjangkau.

# 3. Naikkan stack (dari folder compose Sirius)
docker compose -f /opt/sirius/projects/lifunze/docker-compose.yml \
               -f /opt/sirius/compose/lifunze/docker-compose.sirius.yml \
               --env-file /opt/sirius/compose/lifunze/secrets.env up -d --build
# API menjalankan migrasi Alembic + seed admin otomatis saat start (CMD Dockerfile).

# 4. Caddy: tambahkan blok situs (Caddyfile sirius-caddy), lalu reload caddy
#    lifunze.aditiamh.my.id {
#        handle /api/* { reverse_proxy lifunze-api:8000 }
#        handle        { reverse_proxy lifunze-web:3000 }
#    }
# Sertifikat Let's Encrypt diterbitkan Caddy otomatis (DNS harus menunjuk VPS).

# 5. Backup terjadwal
crontab -e  # tambahkan: 0 3 * * * /opt/sirius/compose/lifunze/backup-db.sh
```

## Verifikasi

```bash
curl -s https://lifunze.aditiamh.my.id/api/v1/health   # {"status":"ok","db":"ok"}
curl -sI https://lifunze.aditiamh.my.id/                # 200 + header keamanan
```

Login sebagai admin seed → WAJIB ganti password (sistem memaksa) → buat guru
pertama dari panel admin. Data production mulai dari bersih (keputusan Fase 0);
tidak ada migrasi dari v1.

## Update rilis berikutnya

```bash
cd /opt/sirius/projects/lifunze && git pull
docker compose -f docker-compose.yml -f /opt/sirius/compose/lifunze/docker-compose.sirius.yml \
  --env-file /opt/sirius/compose/lifunze/secrets.env up -d --build
```

## Catatan keamanan (Fase 8)

- `LIFUNZE_ENV=production` membuat API **menolak menyala** bila FERNET key
  kosong, SECRET_KEY lemah/default, cookie Secure mati, DB bukan PostgreSQL,
  atau password admin seed < 12 karakter.
- Login di-throttle: 5x gagal per username / 10 menit → terkunci 5 menit (429).
- Upload divalidasi **magic bytes**, bukan hanya ekstensi.
- Header keamanan di API & web (nosniff, Referrer-Policy, X-Frame-Options,
  HSTS di production).
- Rahasia hanya di `secrets.env` (600) — tidak pernah di repo.
