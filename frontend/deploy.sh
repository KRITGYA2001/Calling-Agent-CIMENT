#!/usr/bin/env bash
# Build the console and publish it to the VM (served by Caddy next to the API, same origin).
# Usage: bash deploy.sh <ssh-key> [user@host]
set -euo pipefail
KEY="${1:?ssh key path}"; HOST="${2:-ubuntu@140.238.231.135}"
cd "$(dirname "$0")"
VITE_API_BASE_URL= npm run build          # empty = same origin, no CORS, no hard-coded host
scp -i "$KEY" -r dist "$HOST:~/console_dist"
ssh -i "$KEY" "$HOST" 'sudo rm -rf /var/www/console && sudo mkdir -p /var/www && sudo mv ~/console_dist /var/www/console && sudo chmod -R a+rX /var/www/console'
echo "Deployed."
