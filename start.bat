@echo off
pip install -r requirements.txt
python main.py 5000
start "" http://127.0.0.1:5000/
