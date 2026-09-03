#!/bin/bash

# Forcer Python 3.11
if command -v python3.11 &> /dev/null; then
    echo "✅ Python 3.11 trouvé"
    python3.11 bot.py
elif command -v python3.10 &> /dev/null; then
    echo "✅ Python 3.10 trouvé"
    python3.10 bot.py
else
    echo "⚠️ Python 3.11 non trouvé, utilisation de python par défaut"
    python bot.py
fi
