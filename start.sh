#!/bin/bash

TOKEN="$1"

mkdir log > tmp.txt

python -m venv .venv > tmp.txt
source .venv/bin/activate
.venv/bin/python .venv/bin/pip install -r requirements.txt > tmp.txt

export FLASK_APP=main.py

.venv/bin/python main.py > log/flask.log 2>&1 &

export TOKEN
.venv/bin/python bot.py > log/bot.log 2>&1 &

stop_scripts() {
    pkill -f ".venv/bin/python main.py"
    pkill -f ".venv/bin/python bot.py"
    echo 'Процесс завершен'
    exit
}

trap stop_scripts SIGINT

sleep infinity
