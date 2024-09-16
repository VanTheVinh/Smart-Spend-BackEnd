# auth.py
# from flask_cors import CORS
from flask import Blueprint, request, jsonify, session
from modules.db import connect_db

# Tạo blueprint cho các route liên quan đến đăng nhập
auth_bp = Blueprint('auth', __name__)
# CORS(auth_bp)

# Đăng ký
@auth_bp.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    fullname = data.get('fullname')

    if not username or not password:
        return jsonify({"message": "Thiếu tên người dùng hoặc mật khẩu"}), 400

    # Kết nối cơ sở dữ liệu
    conn = connect_db()
    cur = conn.cursor()
    
    # Kiểm tra xem tên người dùng đã tồn tại chưa
    cur.execute('SELECT * FROM "USER" WHERE username = %s', (username,))
    existing_user = cur.fetchone()
    
    if existing_user:
        cur.close()
        conn.close()
        return jsonify({"message": "Tên người dùng đã tồn tại"}), 409

    # Thêm người dùng mới vào cơ sở dữ liệu
    cur.execute('INSERT INTO "USER" (username, password, fullname) VALUES (%s, %s, %s)',
                (username, password, fullname))
    conn.commit()
    cur.close()
    conn.close()

    return jsonify({"message": "Đăng ký thành công"}), 201

# Đăng nhập
@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username or not password:
        return jsonify({"message": "Thiếu tên người dùng hoặc mật khẩu"}), 400

    # Kết nối cơ sở dữ liệu
    conn = connect_db()
    cur = conn.cursor()
    
    # Lấy thông tin người dùng từ cơ sở dữ liệu
    cur.execute('SELECT * FROM "USER" WHERE username = %s', (username,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    if user:
        stored_password = user[2]  # Giả sử mật khẩu là cột thứ 3

        # So sánh mật khẩu
        if password == stored_password:
            # Đăng nhập thành công
            session['user_id'] = user[0]  # Lưu ID người dùng vào phiên
            return jsonify({
                "message": "Đăng nhập thành công",
                "user_id": user[0],
                "username": user[1],
                "fullname": user[2],
            }), 200
        else:
            return jsonify({"message": "Tên người dùng hoặc mật khẩu không đúng"}), 401
    else:
        return jsonify({"message": "Người dùng không tồn tại"}), 404

# Đăng ký
@auth_bp.route('/logout', methods=['POST'])
def logout():
    session.pop('user_id', None)
    return jsonify({"message": "Đăng xuất thành công"}), 200
