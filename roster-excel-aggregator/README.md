# Roster Excel Aggregator

## 1. Google Cloud API key (one-time)

1. Go to https://console.cloud.google.com/ → create a project (or reuse one).
2. APIs & Services → Library → enable "Google Sheets API".
3. APIs & Services → Credentials → Create Credentials → API key.
4. Restrict the key to "Google Sheets API" only.
5. Copy the key — you'll set it as `GOOGLE_API_KEY` below.

## 2. Create login accounts

```bash
cd roster-excel-aggregator
python -c "from app.auth import hash_password; print(hash_password('yourpassword'))"
```

Copy `accounts.json.example` to `accounts.json` and put `"username": "<hash from above>"`.

## 3. Build and run

```bash
docker build -t roster-app .
docker run -d --name roster-app \
  -p 8000:8000 \
  -v roster-data:/data \
  -e GOOGLE_API_KEY=your-key-here \
  -e SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))") \
  roster-app

docker cp accounts.json roster-app:/data/accounts.json
docker restart roster-app
```

## 4. HTTPS via Caddy

Copy `Caddyfile.example` to your Caddy config, replace the domain, reload Caddy.

## 5. Daily new-tab sync (cron)

Add to crontab (`crontab -e`):

```
0 3 * * * docker exec roster-app python -m app.sync_cli >> /var/log/roster-sync.log 2>&1
```

## 6. Using the app

1. Log in with your account.
2. Paste a Google Sheet's spreadsheet ID (the long ID in its URL), click "Load tabs", pick a tab.
3. Click the row that holds staff names, give the doc a label, save — the date range auto-detects.
4. Repeat for each roster doc.
5. Type a staff name, click "Generate .xlsx" — downloads worked hours across every configured doc.
6. If a shift code isn't recognized, it's skipped and listed in the `X-Unmapped-Codes` response header — add it under "Edit code → hours table" with its hour value, then regenerate.
