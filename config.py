# config.py
import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'vinh_secret_key'
    DB_NAME = "spendsmart_db"
    DB_USER = "postgres"
    DB_PASSWORD = "210803"
    DB_HOST = "localhost"
    DB_PORT = "5432"
