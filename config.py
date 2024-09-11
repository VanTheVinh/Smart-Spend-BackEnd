# config.py
import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'secret_key'   
    DB_NAME = "railway"
    DB_USER = "postgres"
    DB_PASSWORD = "nlSqZHxeaiYvjwMkYCFWSElHzWOhLSme"
    DB_HOST = "junction.proxy.rlwy.net"
    DB_PORT = "51474"
