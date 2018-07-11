@echo off
pip install -r requirements.txt
start python tomas.py 5050
start "" http://127.0.0.1:5050/
