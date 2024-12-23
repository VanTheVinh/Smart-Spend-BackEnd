# config.py
import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'secret_key'   
    DB_NAME = "railway"
    DB_USER = "postgres"
    DB_PASSWORD = "nlSqZHxeaiYvjwMkYCFWSElHzWOhLSme"
    DB_HOST = "junction.proxy.rlwy.net"
    DB_PORT = "51474"

 # Cấu hình email
    EMAIL_USERNAME = os.environ.get('EMAIL_USERNAME')
    EMAIL_PASSWORD = os.environ.get('EMAIL_PASSWORD')
    EMAIL_SERVER = os.environ.get('EMAIL_SERVER')
    EMAIL_PORT = os.environ.get('EMAIL_PORT')