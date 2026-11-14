#!/bin/bash
# Fail if git tracks an image or a PDF. Each user makes their own art, and
# generated art does not belong in a public repo.
set -euo pipefail
found=$(git ls-files | grep -i -E '\.(png|jpe?g|webp|gif|pdf|tiff?|heic)$' || true)
if [[ -n "$found" ]]; then
  echo "error: this repo holds no images or PDFs. Remove these from git:" >&2
  echo "$found" >&2
  exit 1
fi
echo "no images or PDFs tracked"
