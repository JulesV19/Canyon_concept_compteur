#!/bin/bash
# Copie le compteur du Mac vers le Pi (par défaut julesvide@compteur.local), dans ~/compteur.
# Sans l'environnement Python du Mac, ses sorties, les images de la doc ni l'outil de carte ;
# le Pi garde son propre environnement et ses propres sorties. En IPv4 : l'IPv6 du Pi décroche.
set -euo pipefail
cd "$(dirname "$0")/../.."

rsync -az --delete -e "ssh -4" \
    --exclude .venv/ --exclude __pycache__/ --exclude .pytest_cache/ --exclude .DS_Store --exclude .claude/ \
    --exclude sorties/ --exclude docs/ --exclude tools/carte/ --exclude 'cartes/*.pmtiles' --exclude 'cartes/*.tmp' \
    ./ "${1:-julesvide@compteur.local}:compteur/"
