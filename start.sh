#!/bin/bash

python -m venv .venv
source .venv/bin/activate
.venv/bin/python .venv/bin/pip install -r requirements.txt

export FLASK_APP=main.py
flask shell
from app import db
db.create_all()
exit()

if command -v apt &> /dev/null; then
    sudo apt install -y pandoc
elif command -v dnf &> /dev/null; then
    sudo dnf install -y pandoc
elif command -v pacman &> /dev/null; then
    sudo pacman -Sy --noconfirm pandoc
fi

.venv/bin/python main.py &
sleep 3

read -p "Введите токен бота если не нужен введите None:" TOKEN
export TOKEN
.venv/bin/python bot.py &

stop_scripts() {
    pkill -f ".venv/bin/python main.py"
    pkill -f ".venv/bin/python bot.py"    
    exit
}

trap stop_scripts SIGINT

sleep infinity
