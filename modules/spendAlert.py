from flask import Blueprint, jsonify, request
import psycopg2
from config import Config

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


# Hàm kiểm tra tồn tại user_id và category_id trong csdl
def validate_user_and_category(user_id, category_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Kiểm tra user_id và category_id có tồn tại không
    cursor.execute(
        """
        SELECT COUNT(*)
        FROM "CATEGORY"
        WHERE user_id = %s AND id = %s
    """,
        (user_id, category_id),
    )
    result = cursor.fetchone()
    conn.close()

    if result[0] == 0:
        return {
            "message": "user_id hoặc category_id không tồn tại trong cơ sở dữ liệu."
        }
    return None


# Hàm kiểm tra và cập nhật thông báo
def check_spend_alert(user_id, category_id):
    conn = get_db_connection()
    cursor = conn.cursor()

    # Lấy thông tin ngân sách và chi tiêu thực tế của danh mục
    cursor.execute(
        """
        SELECT category_name, amount AS budget, actual_amount, category_type
        FROM "CATEGORY"
        WHERE user_id = %s AND id = %s
    """,
        (user_id, category_id),
    )
    category = cursor.fetchone()

    if not category:
        conn.close()
        return (
            jsonify(
                {
                    "message": "user_id hoặc category_id không tồn tại trong cơ sở dữ liệu."
                }
            ),
            400,
        )

    category_name, amount, actual_amount, category_type = category
    amount = float(amount)  # Chuyển đổi sang float

    # Tạo thông báo nếu vượt ngân sách
    alert_message = None
    if category_type == "CHI":  # Trường hợp là khoản chi
        spending_ratio = float(actual_amount) / float(amount) * 100  # Tính tỷ lệ chi tiêu (%)

        if spending_ratio < 60:
            alert_message = f"Bạn đã chi tiêu {round(spending_ratio)}% ngân sách của danh mục {category_name}."
        elif 60 <= spending_ratio < 80:
            alert_message = f"Bạn đã chi tiêu {round(spending_ratio)}%, hãy cân nhắc chi tiêu!"
        elif 80 <= spending_ratio < 100:
            alert_message = f"Bạn đã chi tiêu {round(spending_ratio)}%, sắp vượt ngân sách!"
        else:  # spending_ratio >= 100
            alert_message = f"Bạn đã chi tiêu {round(spending_ratio)}%, vượt ngân sách!"

    elif category_type == "THU":  # Trường hợp là khoản thu
        if actual_amount >= amount:
            alert_message = f"Bạn đã đạt 100% mục tiêu thu nhập trong danh mục {category_name}. Chúc mừng bạn!"
        elif actual_amount < amount:
            alert_message = f"Bạn đã đạt {round((float(actual_amount)/float(amount))*100)}% mục tiêu thu nhập trong danh mục {category_name}. Hãy tiếp tục cố gắng!"


    # Lấy giá trị time_frame từ CATEGORY
    cursor.execute(
        """
        SELECT time_frame 
        FROM "CATEGORY"
        WHERE user_id = %s AND id = %s
    """,
        (user_id, category_id),
    )
    time_frame = cursor.fetchone()

     # Lấy giá trị group_id nếu có, mặc định là None
    group_id = request.args.get("group_id")
    group_id = group_id if group_id else None

    # Thêm thông báo mới
    cursor.execute(
        """
        INSERT INTO "ALERT" (user_id, category_id, alert_message, created_at, group_id)
        VALUES (%s, %s, %s, %s, %s)
    """,
        (user_id, category_id, alert_message, time_frame, group_id),
    )
    conn.commit()

    conn.close()

    # Trả về kết quả kiểm tra
    return {
        "category_name": category_name,
        "amount": amount,
        "actual_amount": actual_amount,
        "alert_message": alert_message,
    }


@spend_alert_bp.route("/post-alert", methods=["POST"])
def post_alert():
    user_id = request.args.get("user_id")  # Lấy user_id từ tham số query string
    category_id = request.args.get("category_id")

    if not user_id or not category_id:
        return jsonify({"message": "user_id hoặc category_id không hợp lệ!"}), 400

    # Gọi hàm kiểm tra lỗi
    validation_error = validate_user_and_category(user_id, category_id)
    if validation_error:
        return jsonify(validation_error), 400

    # Kiểm tra các cảnh báo chi tiêu
    alerts = check_spend_alert(user_id, category_id)

    if not alerts:
        return jsonify({"message": "Không có cảnh báo chi tiêu."})

    # Trả về các cảnh báo chi tiêu
    return jsonify({"alerts": alerts})

# GET ALERT
@spend_alert_bp.route("/get-alert", methods=["GET"])
def get_alert_by_id():
    alert_id = request.args.get("id")  # Lấy id từ query string
    category_id = request.args.get("category_id")
    user_id = request.args.get("user_id")

    if not (alert_id or (category_id and user_id)):
        return jsonify({"message": "Vui lòng cung cấp id hoặc cả category_id và user_id!"}), 400

    conn = get_db_connection()
    if conn is None:
        return jsonify({"message": "Không thể kết nối cơ sở dữ liệu"}), 500

    cursor = conn.cursor()

    try:
        # Tạo câu truy vấn linh hoạt dựa trên tham số
        query = """
            SELECT id, user_id, category_id, alert_message, created_at
            FROM "ALERT"
            WHERE 
        """
        params = []
        if alert_id:
            query += "id = %s"
            params.append(alert_id)
        elif category_id and user_id:
            query += "category_id = %s AND user_id = %s"
            params.extend([category_id, user_id])

        # Thực thi truy vấn
        cursor.execute(query, tuple(params))
        alerts = cursor.fetchall()

        if not alerts:
            return jsonify({"message": "Không tìm thấy thông báo nào!"}), 404

        # Định dạng dữ liệu trả về
        results = [
            {
                "id": alert[0],
                "user_id": alert[1],
                "category_id": alert[2],
                "alert_message": alert[3],
                "created_at": alert[4].strftime("%d/%m/%Y"),
            }
            for alert in alerts
        ]

        return jsonify({"alerts": results}), 200

    except Exception as e:
        return jsonify({"message": f"Lỗi khi lấy thông báo: {str(e)}"}), 500

    finally:
        cursor.close()
        conn.close()


@spend_alert_bp.route("/delete-alert", methods=["DELETE"])
def delete_alert_by_id():
    alert_id = request.args.get("alert_id")  # Lấy alert_id từ query string

    if not alert_id:
        return jsonify({"message": "alert_id không hợp lệ!"}), 400

    conn = get_db_connection()
    if conn is None:
        return jsonify({"message": "Không thể kết nối cơ sở dữ liệu"}), 500

    cursor = conn.cursor()

    try:
        # Kiểm tra xem thông báo có tồn tại hay không
        cursor.execute(
            """
            SELECT id
            FROM "ALERT"
            WHERE id = %s
        """,
            (alert_id,),
        )
        alert = cursor.fetchone()

        if not alert:
            return jsonify({"message": "Thông báo không tồn tại hoặc đã bị xóa."}), 404

        # Xóa thông báo
        cursor.execute(
            """
            DELETE FROM "ALERT"
            WHERE id = %s
        """,
            (alert_id,),
        )
        conn.commit()
        return jsonify({"message": "Đã xóa thông báo thành công."}), 200

    except Exception as e:
        return jsonify({"message": f"Lỗi khi xóa thông báo: {str(e)}"}), 500

    finally:
        cursor.close()
        conn.close()
