# AEPFM: Auction Ethiopia Processing Fee Management

Web system that automates the processing-fee step after an auction: import winners, generate invoices and Amharic PDF payment letters, send SMS with a public payment link, verify payment receipts automatically (Verify.ET for CBE transfers + Gemini receipt reading), and send unclear cases to staff review.

## Stack

- Django + Django REST Framework (Python 3.12, gunicorn)
- React + Vite
- PostgreSQL (Neon, pooled connection)
- Backblaze B2 (files)
- WeasyPrint (PDF, Amharic via Noto fonts)
- Afro Message (SMS)
- Verify.ET
- Gemini
- Sentry

## Production

- Frontend: https://pay.auctionethiopia.et (nginx serves static files from /var/www/aepfm-frontend)
- API: https://payapi.auctionethiopia.et (nginx -> gunicorn 127.0.0.1:8000, systemd service `aepfm`)
- Server: DigitalOcean droplet, Ubuntu 24.04, user `aepfm`, SSH key only.
- Daily overdue job: systemd timer `aepfm-overdue.timer` (06:00 UTC) calls /api/cron/flag-overdue/ with a secret header.
- Health check: https://payapi.auctionethiopia.et/health/

## Local development

```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill the values (never commit `.env`).

```bash
python manage.py migrate
python manage.py runserver
```

Frontend:
```bash
cd front-end_crm
npm ci
npm run dev
```

Tests:
```bash
python manage.py test
```

## Deploying

### Backend
Push to GitHub, then on the server run:
```bash
bash deploy.sh
```
(Pushing alone deploys nothing.)

### Frontend
From your PC run:
```powershell
.\deploy-frontend.ps1
```
(builds with the production API URL, copies `dist` to the server, fixes permissions.)

## Operations

- Logs: `sudo journalctl -u aepfm -f`
- Restart: `sudo systemctl restart aepfm`
- nginx test/reload: `sudo nginx -t && sudo systemctl reload nginx`
- Certificates renew automatically (Certbot); check with `sudo certbot renew --dry-run`.
- Errors go to Sentry. Receipt reading failures go to the staff review queue.
- Timeouts must nest: Gemini request (~60s) < gunicorn `--timeout 90` < nginx `proxy_read_timeout 90s`.
- The `.env` lives only on the server (`/home/aepfm/AEPFM/.env`, mode 600). Keep an encrypted backup elsewhere.
- systemd `EnvironmentFile` does not strip quotes: write values unquoted.

## Companion project

A separate Call Center CRM (hosted on Render) pulls verified winners through the export API using a service API key created in the admin site.
## how to update vps back end
ssh aepfm@68.183.216.61
cd ~/AEPFM
bash deploy.sh