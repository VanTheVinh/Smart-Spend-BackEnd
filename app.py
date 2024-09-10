# app.py
from flask import Flask
from flask_cors import CORS
from config import Config
from modules.auth import auth_bp  
from modules.invoice_process import invoice_process_bp  

app = Flask(__name__)
app.config['SECRET_KEY'] = Config.SECRET_KEY

# Cấu hình CORS cho tất cả các route
CORS(app)

# Đăng ký blueprint cho các route   
app.register_blueprint(auth_bp)
app.register_blueprint(invoice_process_bp) 

if __name__ == '__main__':
    app.run(debug=True)
