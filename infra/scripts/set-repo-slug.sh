#!/usr/bin/env bash
# Replace the 1811tushar/NexusAI placeholder in README badges and docs: bash infra/scripts/set-repo-slug.sh yourname/nexusai
set -euo pipefail
slug="${1:?Usage: $0 1811tushar/NexusAI}"; [[ "$slug" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || { echo "Slug must look like owner/repo" >&2; exit 2; }
cd "$(dirname "$0")/../.."
grep -rIl --exclude-dir=.git --exclude-dir=node_modules '1811tushar/NexusAI' . | while read -r f; do sed -i "s#1811tushar/NexusAI#$slug#g" "$f"; echo "updated $f"; done
