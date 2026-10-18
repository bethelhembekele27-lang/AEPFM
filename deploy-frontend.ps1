# Frontend deploy for AEPFM. Run on your PC (PowerShell) from the repo root.
# Set the two values below once (or export them in your shell first).
$env:VITE_API_BASE = "https://payapi.auctionethiopia.et"
# $env:VITE_GOOGLE_CLIENT_ID = "<your Google client id>"   # required, do not commit it

Set-Location front-end_crm   # <-- change if your frontend folder has a different name
npm ci
npm run build
scp -r dist/* aepfm@68.183.216.61:/var/www/aepfm-frontend/
ssh aepfm@68.183.216.61 "sudo chmod -R o+rX /var/www/aepfm-frontend"
Write-Host "Frontend deployed. Hard-refresh the site (Ctrl+F5)."
