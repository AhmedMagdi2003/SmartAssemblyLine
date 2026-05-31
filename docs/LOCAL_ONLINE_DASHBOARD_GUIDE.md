# Local Online Dashboard Guide

This mode keeps the whole Smart Assembly Line system local:

- PostgreSQL stays local
- Mosquitto stays local
- logger stays local
- dashboard stays local
- vision pipeline stays local

Only the dashboard URL is published to the internet.

## Best Fit

Use this when:

- the factory PC should remain the only runtime machine
- managers need to open the dashboard from home
- you do not want to move the database or logger to cloud yet

## Recommended Tunnel Choice

This repo now supports Cloudflare Tunnel launchers for the dashboard.

Why this is the recommended path:

- Cloudflare Tunnel is available on all plans
- it creates an outbound-only tunnel
- you do not need to open router ports
- Cloudflare documents a quick free development tunnel and a named tunnel for production

Official references:

- [Cloudflare Tunnel overview](https://developers.cloudflare.com/tunnel/)
- [Set up Cloudflare Tunnel](https://developers.cloudflare.com/tunnel/setup/)
- [Quick Tunnels / TryCloudflare](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/do-more-with-tunnels/trycloudflare/)
- [Locally-managed tunnels](https://developers.cloudflare.com/tunnel/advanced/local-management/index.md)

## Files Added

- `deployment/cloud/env/dashboard-tunnel.env.example`
- `scripts/start_dashboard_tunnel.sh`
- `scripts/start_dashboard_tunnel.ps1`

## Two Ways To Use It

### 1. Quick public link for testing

This gives you a temporary `trycloudflare.com` URL.

1. Start the local stack first
2. Start the tunnel script
3. Share the printed URL

WSL / Ubuntu:

```bash
bash scripts/start_local_stack.sh
```

In another terminal:

```bash
bash scripts/start_dashboard_tunnel.sh
```

Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_local_stack.ps1
```

Then in another PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_dashboard_tunnel.ps1
```

Cloudflare will print the public URL in the tunnel terminal.

### 2. Stable online address

If you want a fixed public hostname such as:

```text
dashboard.example.com
```

use a named Cloudflare Tunnel.

Create:

```text
deployment/cloud/env/dashboard-tunnel.env
```

from:

```text
deployment/cloud/env/dashboard-tunnel.env.example
```

Set:

```env
DASHBOARD_HOST=127.0.0.1
DASHBOARD_PORT=8000
CLOUDFLARE_TUNNEL_TOKEN=your-token-here
```

Then run:

WSL / Ubuntu:

```bash
bash scripts/start_dashboard_tunnel.sh
```

Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File scripts/start_dashboard_tunnel.ps1
```

The token-based tunnel is the correct mode when you want a fixed online address.

## Recommended Run Order

1. start the local stack
2. verify the local dashboard opens at `http://127.0.0.1:8000`
3. start the dashboard tunnel
4. open the public URL from another network

## Important Notes

- if the local PC turns off, the public dashboard stops too
- if the local internet connection drops, remote users lose access
- quick tunnels are good for testing, not long-term production
- a stable hostname needs a named Cloudflare Tunnel
- the dashboard is only as current as the local PC runtime

## Security Advice

For remote management, prefer the stable tunnel path over raw port forwarding.

Avoid:

- opening router port `8000` directly to the internet
- exposing PostgreSQL or Mosquitto publicly

Only the dashboard should be published.
