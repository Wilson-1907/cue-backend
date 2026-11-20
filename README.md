# CUE Backend

Full CUE water-monitoring API + hosted UI templates + Uno agent scripts.

## Render

Connect this repo in Render → **New → Blueprint** (uses `render.yaml`).

See [RENDER.md](RENDER.md).

## Local

```bash
pip install -r requirements.txt
python manage.py migrate
python manage.py runserver
```

## Uno listening (your PC)

USB listening runs on your Windows machine and posts to this API:

```powershell
cd scripts\uno_agent
# set api_base to your Render URL in config.json
.\install_windows_autostart.ps1
```
