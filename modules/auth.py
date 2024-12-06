import jwt
import bcrypt
from flask import Blueprint, request, jsonify, make_response
from datetime import datetime, timedelta, timezone
from modules.db import connect_db

# Tạo blueprint cho các route liên quan đến đăng nhập
auth_bp = Blueprint('auth', __name__)
SECRET_KEY = "your_secret_key_here"  # Khóa bí mật dùng để ký JWT

# Hàm tạo Access Token
def generate_access_token(user_id):
    expiration = datetime.now(timezone.utc) + timedelta(hours=1)
    # Token có hiệu lực trong 1 giờ
    payload = {
        "user_id": user_id,
        "exp": expiration
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

# Middleware kiểm tra Access Token
def token_required(func):
    def wrapper(*args, **kwargs):
        # Lấy token từ cookie thay vì header
        token = request.cookies.get("access_token")

        if not token:
            return jsonify({"message": "Access Token không hợp lệ"}), 401

        try:
            decoded_token = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            request.user_id = decoded_token["user_id"]
        except jwt.ExpiredSignatureError:
            print("Lỗi: Token đã hết hạn")
            return jsonify({"message": "Token đã hết hạn"}), 401
        except jwt.InvalidTokenError as e:
            print(f"Lỗi: Token không hợp lệ - {e}")
            return jsonify({"message": "Token không hợp lệ"}), 401

        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper

# Đăng ký
@auth_bp.route('/register', methods=['POST'])
def register():
    from datetime import datetime

    data = request.get_json()
    username = data.get('username')
    password = data.get('password')
    fullname = data.get('fullname')
    avatar = data.get('avatar')  # Tùy chọn, có thể không có

    if not username:
        return jsonify({"message": "Thiếu tên người dùng"}), 400
    if not password:
        return jsonify({"message": "Thiếu mật khẩu"}), 400
    if not fullname:
        return jsonify({"message": "Thiếu tên đầy đủ"}), 400

    conn = connect_db()
    cur = conn.cursor()

    # Kiểm tra tên người dùng đã tồn tại
    cur.execute('SELECT * FROM "USER" WHERE username = %s', (username,))
    existing_user = cur.fetchone()

    if existing_user:
        cur.close()
        conn.close()
        return jsonify({"message": "Tên người dùng đã tồn tại"}), 409

    # Mã hóa mật khẩu
    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

    # Ngày hiện tại (ngày đăng ký)
    today_date = datetime.now().strftime('%Y-%m-%d')

    # Thêm người dùng mới
    cur.execute(
        'INSERT INTO "USER" (username, password, fullname, avatar) VALUES (%s, %s, %s, %s) RETURNING id',
        (username, hashed_password, fullname, avatar)
    )
    user_id = cur.fetchone()[0]
    conn.commit()

    # Thêm các danh mục mặc định
    DEFAULT_CATEGORIES = [
        {"category_name": "Lương", "category_type": "THU"},
        {"category_name": "Thu nhập khác", "category_type": "THU"},
        {"category_name": "Tiền chuyển đến", "category_type": "THU"},

        {"category_name": "Ăn uống", "category_type": "CHI"},
        {"category_name": "Di chuyển", "category_type": "CHI"},
        {"category_name": "Tiện ích (Thuê nhà, điện, nước, wifi, internet, ...)", "category_type": "CHI"},
        {"category_name": "Giải trí", "category_type": "CHI"},
        {"category_name": "Khác", "category_type": "CHI"},
    ]

    try:
        for category in DEFAULT_CATEGORIES:
            # Kiểm tra amount và actual_amount, gán giá trị mặc định nếu cần
            percentage_limit = category.get('percentage_limit', 0) or 0
            amount = category.get('amount', 0) or 0  # Mặc định là 1 nếu không có hoặc giá trị là None
            actual_amount = category.get('actual_amount', 0) or 0  # Tương tự với actual_amount

            cur.execute(
                '''
                INSERT INTO "CATEGORY" (user_id, category_name, category_type, percentage_limit, amount, actual_amount, time_frame)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                ''',
                (user_id, category['category_name'], category['category_type'], percentage_limit, amount, actual_amount, today_date)
            )
        conn.commit()
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        return jsonify({"message": f"Lỗi khi thêm danh mục mặc định: {str(e)}"}), 500

    cur.close()
    conn.close()
    return jsonify({"message": "Đăng ký thành công"}), 201


# Đăng nhập
@auth_bp.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    username = data.get('username')
    password = data.get('password')

    if not username:
        return jsonify({"message": "Thiếu tên người dùng"}), 400
    if not password:
        return jsonify({"message": "Thiếu mật khẩu"}), 400
    if not username and not password:
        return jsonify({"message": "Thiếu tên người dùng và mật khẩu"}), 400

    conn = connect_db()
    cur = conn.cursor()
    cur.execute('SELECT id, username, fullname, avatar, password, budget FROM "USER" WHERE username = %s', (username,))
    user = cur.fetchone()
    cur.close()
    conn.close()

    if user:
        user_id, stored_username, fullname, avatar, stored_password, budget = user

        try:
            # Kiểm tra mật khẩu
            if bcrypt.checkpw(password.encode('utf-8'), stored_password.encode('utf-8')):
                # Tạo Access Token
                token = generate_access_token(user_id)
                
                # Lưu token vào cookie
                response = make_response(jsonify({
                    "message": "Đăng nhập thành công",
                    "user_info": {
                        "user_id": user_id,
                        "username": stored_username,
                        "fullname": fullname,
                        "avatar": avatar,
                        "budget": budget,
                    }
                }), 200)
                
                # Lưu token vào cookie với tên 'access_token'
                response.set_cookie('access_token', token, max_age=3600, secure=True, httponly=True, samesite='Strict')

                return response
            else:
                return jsonify({"message": "Tên người dùng hoặc mật khẩu không đúng"}), 401
        except ValueError as e:
            print(f"Lỗi giải mã mật khẩu: {e}")
            return jsonify({"message": "Mật khẩu trong cơ sở dữ liệu không hợp lệ"}), 500
    else:
        return jsonify({"message": "Người dùng không tồn tại"}), 404

# Đăng xuất
@auth_bp.route('/logout', methods=['POST'])
def logout():
    response = make_response(jsonify({"message": "Đăng xuất thành công"}), 200)
    response.delete_cookie('access_token')  # Xóa cookie chứa token
    return response

# Kiểm tra phiên đăng nhập
@auth_bp.route('/protected', methods=['GET'])
@token_required
def protected():
    return jsonify({"message": f"Phiên đăng nhập hợp lệ cho user_id: {request.user_id}"}), 200


# @auth_bp.route('/user-info', methods=['GET'])
# @jwt_required()  # Xác thực bằng JWT
# def user_info():
#     user_id = get_jwt_identity()  # Lấy user_id từ token
#     conn = connect_db()
#     cur = conn.cursor()
#     cur.execute('SELECT username, fullname, avatar, budget FROM "USER" WHERE id = %s', (user_id,))
#     user = cur.fetchone()
#     cur.close()
#     conn.close()

#     if user:
#         username, fullname, avatar, budget = user
#         return jsonify({
#             "status": "success",
#             "user_info": {
#                 "username": username,
#                 "fullname": fullname,
#                 "avatar": avatar,
#                 "budget": budget,
#             }
#         }), 200
#     return jsonify({"status": "error", "message": "Người dùng không tồn tại"}), 404



# Xóa người dùng
@auth_bp.route('/delete-user/<int:user_id>', methods=['DELETE'])
# @token_required
def delete_user(user_id):
    conn = connect_db()
    cur = conn.cursor()

    try:
        # Kiểm tra xem người dùng có tồn tại không
        cur.execute('SELECT id FROM "USER" WHERE id = %s', (user_id,))
        user = cur.fetchone()

        if not user:
            cur.close()
            conn.close()
            return jsonify({"message": "Người dùng không tồn tại"}), 404

        # Xóa người dùng
        cur.execute('DELETE FROM "USER" WHERE id = %s', (user_id,))
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"message": "Xóa người dùng thành công"}), 200
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        return jsonify({"message": f"Lỗi khi xóa người dùng: {str(e)}"}), 500
