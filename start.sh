#!/bin/bash

exec > /dev/null 2>&1

TOKEN="$1"

mkdir log

python -m venv .venv
source .venv/bin/activate
.venv/bin/python .venv/bin/pip install -r requirements.txt

export FLASK_APP=main.py

flask shell -c "
from app import db
db.create_all()
"

if command -v apt &> /dev/null; then
    sudo apt install -y pandoc
elif command -v dnf &> /dev/null; then
    sudo dnf install -y pandoc
elif command -v pacman &> /dev/null; then
    sudo pacman -S --noconfirm pandoc
fi

.venv/bin/python main.py > log/flask.log 2>&1 &

export TOKEN
.venv/bin/python bot.py > log/bot.log 2>&1 &

stop_scripts() {
    pkill -f ".venv/bin/python main.py"
    pkill -f ".venv/bin/python bot.py"    
    exit
}

trap stop_scripts SIGINT

sleep infinity
