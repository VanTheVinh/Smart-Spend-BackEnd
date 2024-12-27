from flask import Blueprint, request, jsonify, current_app
from flask_mail import Mail, Message
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from werkzeug.security import generate_password_hash
from modules.db import connect_db
from flask_bcrypt import bcrypt
from config import Config

reset_password_bp = Blueprint('reset_password', __name__)

# Khởi tạo Flask-Mail
mail = Mail()

def init_mail(app):
    """Cấu hình và khởi tạo Mail"""
    app.config.update({
        'MAIL_SERVER': 'smtp.gmail.com',
        'MAIL_PORT': 587,
        'MAIL_USE_TLS': True,
        'MAIL_USE_SSL': False,
        'MAIL_USERNAME': Config.MAIL_USERNAME,
        'MAIL_PASSWORD': Config.MAIL_PASSWORD,
        'MAIL_DEFAULT_SENDER': Config.MAIL_DEFAULT_SENDER
    })
    mail.init_app(app)

# Tạo một đối tượng serializer để tạo và giải mã token
def get_serializer():
    return URLSafeTimedSerializer(current_app.config['SECRET_KEY'])

def generate_reset_token(email):
    serializer = get_serializer()
    return serializer.dumps(email, salt=current_app.config['SECURITY_PASSWORD_SALT'])

# Xử lý yêu cầu reset mật khẩu
@reset_password_bp.route('/reset-password', methods=['POST'])
def reset_password():
    data = request.json
    email = data.get('email')

    if not email:
        return jsonify({"status": "error", "message": "Email không được để trống"}), 400

    try:
        token = generate_reset_token(email)
        reset_url = f"http://localhost:3000/#/reset-password/{token}" 

        subject = "Yêu cầu đặt lại mật khẩu"
        body = (f"Xin chào,\n\nBạn đã yêu cầu đặt lại mật khẩu. Vui lòng nhấp vào liên kết dưới đây để đặt lại mật khẩu của bạn:\n"
                f"{reset_url}\n\nNếu bạn không yêu cầu đặt lại mật khẩu, vui lòng bỏ qua email này.")

        msg = Message(subject, recipients=[email], body=body)
        mail.send(msg)

        return jsonify({"status": "success", "message": "Email đặt lại mật khẩu đã được gửi thành công"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# API xử lý mật khẩu mới
@reset_password_bp.route('/reset-password/<token>', methods=['POST'])
def reset_password_submit(token):
    data = request.json
    new_password = data.get('password')

    if not new_password:
        return jsonify({"status": "error", "message": "Mật khẩu không được để trống"}), 400

    try:
        email = get_serializer().loads(token, salt=current_app.config['SECURITY_PASSWORD_SALT'], max_age=3600)
        
        with connect_db() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT * FROM "USER" WHERE email = %s', (email,))
                user = cur.fetchone()

                if not user:
                    return jsonify({"status": "error", "message": "Người dùng không tồn tại"}), 400

                # Mã hóa mật khẩu mới sử dụng bcrypt
                hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
                
                cur.execute('UPDATE "USER" SET password = %s WHERE email = %s', (hashed_password, email))
                conn.commit()

        return jsonify({"status": "success", "message": "Mật khẩu đã được thay đổi thành công"}), 200
    except SignatureExpired:
        return jsonify({"status": "error", "message": "Token đã hết hạn"}), 400
    except BadSignature:
        return jsonify({"status": "error", "message": "Token không hợp lệ"}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# API cập nhật mật khẩu theo user_id
@reset_password_bp.route('/update-password/<int:user_id>', methods=['PUT'])
def update_password(user_id):
    try:
        data = request.json
        new_password = data.get('password')

        if not new_password:
            return jsonify({"status": "error", "message": "Mật khẩu mới không được để trống"}), 400

        # Mã hóa mật khẩu mới
        hashed_password = bcrypt.hashpw(new_password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


        with connect_db() as conn:
            with conn.cursor() as cur:
                cur.execute('SELECT id FROM "USER" WHERE id = %s', (user_id,))
                user = cur.fetchone()

                if not user:
                    return jsonify({"status": "error", "message": "Người dùng không tồn tại"}), 404

                cur.execute('UPDATE "USER" SET password = %s WHERE id = %s', (hashed_password, user_id))
                conn.commit()

        return jsonify({"status": "success", "message": "Mật khẩu đã được cập nhật thành công"}), 200
    except Exception as e:
        return jsonify({"status": "error", "message": "Đã xảy ra lỗi trong quá trình xử lý"}), 500
