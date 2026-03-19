#!/bin/bash
# Project Sovereign - Alpha Launcher

# Lade .env
source .env

echo "🚀 Starte Project Sovereign..."

# Validierung nur für kritische Keys
if [[ "$ANTHROPIC_API_KEY" == *"REPLACE_ME"* ]]; then
  echo "❌ FEHLER: ANTHROPIC_API_KEY fehlt!"
  exit 1
fi

if [[ "$TELEGRAM_BOT_TOKEN" == *"REPLACE_ME"* ]]; then
  echo "⚠️ WARNUNG: Telegram Token fehlt. CEO wird stumm sein."
fi

# Starte Docker-Infrastruktur
docker compose up -d --build

echo "✅ CEO-Container läuft."
echo "📺 Nutze 'docker logs -f sovereign-ceo' um den Denkprozess zu sehen."
