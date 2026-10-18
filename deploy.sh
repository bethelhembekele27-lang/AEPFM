#!/usr/bin/env bash
# Backend deploy for AEPFM. Run ON THE VPS as user aepfm:  bash deploy.sh
set -euo pipefail
cd ~/AEPFM
source venv/bin/activate
git pull origin main
pip install -r requirements.txt
set -a; source <(grep -v '^#' .env | sed '/^$/d'); set +a
python manage.py migrate --noinput
python manage.py collectstatic --noinput
sudo systemctl restart aepfm
sleep 2
curl -fsS https://payapi.auctionethiopia.et/health/ && echo && echo "Deploy OK"
