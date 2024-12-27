# config.py
import os


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY") or "secret_key"
    DB_NAME = "railway"
    DB_USER = "postgres"
    DB_PASSWORD = "nlSqZHxeaiYvjwMkYCFWSElHzWOhLSme"
    DB_HOST = "junction.proxy.rlwy.net"
    DB_PORT = "51474"

    
    SECURITY_PASSWORD_SALT = 'c9f85f0a741e3c5ea1d1b2b8b118cf6b'  # Salt cho việc tạo token reset mật khẩu
    MAIL_USERNAME = 'vinhvt21@gmail.com'
    MAIL_PASSWORD = 'yvsk jeux bpih rkqs'
    MAIL_DEFAULT_SENDER = 'vinhvt21@gmail.com'
   
