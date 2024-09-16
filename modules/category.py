from flask import Blueprint, request, jsonify
from modules.db import connect_db

category_bp = Blueprint("category", __name__)

# Route để thêm danh mục mới
@category_bp.route("/add-category", methods=["POST"])
def add_category():
    data = request.get_json()

    # Lấy ra các trường cần thiết
    category_type = data.get("category_type")
    category_name = data.get("category_name")
    percentage_limit = data.get("percentage_limit")
    amount = data.get("amount")
    time_frame = data.get("time_frame")
    user_id = data.get("user_id")

    # Kiểm tra các trường bắt buộc
    if not category_type or not category_name or not time_frame or not user_id:
        return jsonify({"message": "Thiếu thông tin bắt buộc"}), 400

    conn = connect_db()
    cur = conn.cursor()

    try:
        # Chèn dữ liệu vào bảng CATEGORY
        cur.execute(
            'INSERT INTO "CATEGORY" (category_type, category_name, percentage_limit, amount, time_frame, user_id) VALUES (%s, %s, %s, %s, %s, %s)',
            (
                category_type,
                category_name,
                percentage_limit,
                amount,
                time_frame,
                user_id,
            ),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        return jsonify({"message": f"Lỗi khi thêm danh mục: {str(e)}"}), 500

    cur.close()
    conn.close()

    return jsonify({"message": "Thêm danh mục thành công"}), 201
