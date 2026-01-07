# src/db.py
import os
import sqlite3

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(BASE_DIR, "meta_sales_trigger.db")

def get_conn():
    return sqlite3.connect(DB_PATH)
