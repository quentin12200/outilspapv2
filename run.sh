#!/usr/bin/env bash
set -e
python -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -r requirements.txt
cp -n .env.example .env || true
uvicorn app.main:app --reload --port 8000
