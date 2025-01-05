from flask import Blueprint, jsonify, request
import psycopg2
from config import Config
from datetime import datetime

spend_alert_bp = Blueprint("spend-alert", __name__)

def get_db_connection():
    try:
        # Kết nối với cơ sở dữ liệu
        conn = psycopg2.connect(
            database=Config.DB_NAME,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            host=Config.DB_HOST,
            port=Config.DB_PORT,
        )
        return conn
    except Exception as e:
        print(f"Lỗi kết nối cơ sở dữ liệu: {str(e)}")
        return None

# Hàm kiểm tra tồn tại user_id trong CSDL
def validate_user(user_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Kiểm tra user_id có tồn tại không
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM "USER"
        WHERE id = %s
    """,
        (user_id,),
    )
    result = cursor.fetchone()
    conn.close()

    if result[0] == 0:
        return {"message": "user_id không tồn tại trong cơ sở dữ liệu."}
    return None

# Hàm lấy ngày hiện tại theo định dạng dd-mm-yyyy
def get_current_date():
    return datetime.now().strftime('%d-%m-%Y')

# Phương thức POST để kiểm tra cảnh báo chi tiêu
@spend_alert_bp.route('/check-alerts', methods=['POST'])
def check_alerts():
    # Nhận tham số từ request
    user_id = request.json.get('user_id')

    # Kiểm tra xem user_id có hợp lệ không
    validation_error = validate_user(user_id)
    if validation_error:
        return jsonify(validation_error), 400

    conn = get_db_connection()
    cursor = conn.cursor()

    # Truy vấn tất cả danh mục của người dùng
    cursor.execute(""" 
        SELECT category_name, actual_amount, amount, time_frame
        FROM "CATEGORY"
        WHERE user_id = %s
    """, (user_id,))

    categories = cursor.fetchall()
    conn.close()

    alerts = []
    current_date = get_current_date()  # Lấy ngày hiện tại

    for category in categories:
        category_name, actual_amount, amount, time_frame = category

        if amount == 0:
            # Bỏ qua các mục có ngân sách bằng 0
            continue

        spending_ratio = (actual_amount / amount) * 100

        # Điều kiện cảnh báo chi tiêu
        alert = {
            "category_name": category_name,
            "date": current_date  # Ngày hiện tại sẽ là một trường riêng
        }

        if spending_ratio > 100:
            alert["message"] = f"Cảnh báo: {category_name} đã vượt quá giới hạn ngân sách, chi tiêu {spending_ratio:.2f}%."
            alerts.append(alert)
        elif 70 <= spending_ratio <= 100:
            alert["message"] = f"Danh mục {category_name} đã chi tiêu {spending_ratio:.2f}% của ngân sách."
            alerts.append(alert)

    # Nếu có cảnh báo, trả về danh sách cảnh báo
    if alerts:
        return jsonify(alerts), 200
    else:
        # Nếu không có cảnh báo, trả về thông báo không có
        return jsonify({"status": "success", "message": "Không có cảnh báo chi tiêu."}), 200
