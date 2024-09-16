# app.py
from flask import Flask
from flask_cors import CORS
from config import Config
from modules.auth import auth_bp  
from modules.bill import bill_bp  
from modules.category import category_bp  

app = Flask(__name__)
app.config['SECRET_KEY'] = Config.SECRET_KEY

# Cấu hình CORS cho tất cả các route
CORS(app)

# Đăng ký blueprint cho các route   
app.register_blueprint(auth_bp)
app.register_blueprint(bill_bp) 
app.register_blueprint(category_bp) 

if __name__ == '__main__':
    app.run(debug=True)
