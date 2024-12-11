from flask import Blueprint, request, jsonify
from modules.db import connect_db
from datetime import datetime, timedelta
import psycopg2.extras
import requests


category_bp = Blueprint("category", __name__)

# Hàm để tính ngày cuối cùng của tháng
def get_end_of_month(year, month):
    # Tạo ngày đầu tiên của tháng sau
    next_month = month % 12 + 1
    next_year = year if month < 12 else year + 1
    first_day_of_next_month = datetime(next_year, next_month, 1)
    
    # Ngày cuối cùng của tháng hiện tại là ngày trước ngày đầu tiên của tháng sau
    end_of_month = first_day_of_next_month - timedelta(days=1)
    return end_of_month


# Route để thêm danh mục mới
@category_bp.route("/add-category", methods=["POST"])
def add_category():
    data = request.get_json()

    # Lấy ra các trường cần thiết
    category_type = data.get("category_type")
    category_name = data.get("category_name")
    percentage_limit = data.get("percentage_limit", 0)
    amount = data.get("amount", 0)
    time_frame = data.get("time_frame")
    user_id = data.get("user_id")

    # Kiểm tra các trường bắt buộc
    if not category_type or not category_name or not time_frame or not user_id:
        return jsonify({"message": "Thiếu thông tin bắt buộc"}), 400

    # Kiểm tra tính hợp lệ của category_type
    if category_type not in ["CHI", "THU"]:
        return jsonify({"message": "category_type phải là 'CHI' hoặc 'THU'"}), 400

    # Kiểm tra tính hợp lệ của percentage_limit nếu có
    if percentage_limit is not None:
        try:
            percentage_limit = float(percentage_limit)
            if percentage_limit < 0 or percentage_limit > 100:
                return (
                    jsonify(
                        {"message": "percentage_limit phải trong khoảng từ 0 đến 100"}
                    ),
                    400,
                )
        except ValueError:
            return jsonify({"message": "percentage_limit không hợp lệ"}), 400

    # Kiểm tra tính hợp lệ của amount nếu có
    if amount is not None:
        try:
            amount = float(amount)
            if amount < 0:
                return jsonify({"message": "amount không thể âm"}), 400
        except ValueError:
            return jsonify({"message": "amount không hợp lệ"}), 400

    # Kiểm tra và chuyển đổi time_frame sang định dạng yyyy-mm-dd
    try:
        # Chuyển time_frame từ dd-mm-yyyy sang yyyy-mm-dd
        time_frame = datetime.strptime(time_frame, "%d-%m-%Y").strftime("%Y-%m-%d")
    except ValueError:
        return jsonify({"message": "time_frame phải có định dạng dd-mm-yyyy"}), 400

    conn = connect_db()
    cur = conn.cursor()

    try:
        # Kiểm tra xem danh mục đã tồn tại cho người dùng này chưa
        cur.execute(
            'SELECT * FROM "CATEGORY" WHERE category_name = %s AND user_id = %s',
            (category_name, user_id),
        )
        existing_category = cur.fetchone()
        if existing_category:
            cur.close()
            conn.close()
            return jsonify({"message": "Danh mục đã tồn tại cho người dùng này"}), 400

        # Chèn dữ liệu vào bảng CATEGORY
        else:
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

# Cập nhật category
@category_bp.route("/update-category/<int:category_id>", methods=["PUT"])
def update_category(category_id):
    data = request.get_json()

    # Lấy ra các trường cần cập nhật
    category_type = data.get("category_type")
    category_name = data.get("category_name")
    percentage_limit = data.get("percentage_limit")
    amount = data.get("amount")
    actual_amount = data.get("actual_amount")
    time_frame = data.get("time_frame")

    # Kiểm tra nếu không có trường nào được cung cấp để cập nhật
    if not any([category_type, category_name, percentage_limit, amount, actual_amount, time_frame]):
        return jsonify({"message": "Không có thông tin để cập nhật"}), 400

    # Kiểm tra tính hợp lệ của category_type nếu có
    if category_type and category_type not in ["CHI", "THU"]:
        return jsonify({"message": "category_type phải là 'CHI' hoặc 'THU'"}), 400

    # Kiểm tra tính hợp lệ của percentage_limit nếu có
    if percentage_limit is not None:
        try:
            percentage_limit = float(percentage_limit)
            if percentage_limit < 0 or percentage_limit > 100:
                return (
                    jsonify(
                        {"message": "percentage_limit phải trong khoảng từ 0 đến 100"}
                    ),
                    400,
                )
        except ValueError:
            return jsonify({"message": "percentage_limit không hợp lệ"}), 400

    # Kiểm tra tính hợp lệ của amount nếu có
    if amount is not None:
        try:
            amount = float(amount)
            if amount < 0:
                return jsonify({"message": "amount không thể âm"}), 400
        except ValueError:
            return jsonify({"message": "amount không hợp lệ"}), 400

    # Kiểm tra tính hợp lệ của actual_amount nếu có
    if actual_amount is not None:
        try:
            actual_amount = float(actual_amount)
            if actual_amount < 0:
                return jsonify({"message": "actual_amount không thể âm"}), 400
        except ValueError:
            return jsonify({"message": "actual_amount không hợp lệ"}), 400


    # Kiểm tra và chuyển đổi time_frame sang định dạng yyyy-mm-dd
    try:
        # Chuyển time_frame từ dd-mm-yyyy sang yyyy-mm-dd
        time_frame = datetime.strptime(time_frame, "%d-%m-%Y").strftime("%Y-%m-%d")
    except ValueError:
        return jsonify({"message": "time_frame phải có định dạng dd-mm-yyyy"}), 400

    conn = connect_db()
    cur = conn.cursor()


    # Nếu percentage_limit được cung cấp, tính toán lại amount
    # if percentage_limit is not None:
    #     try:
    #         # Lấy user_id từ danh mục hiện tại
    #         cur.execute('SELECT user_id FROM "CATEGORY" WHERE id = %s', [category_id])
    #         user_result = cur.fetchone()
    #         if not user_result:
    #             cur.close()
    #             conn.close()
    #             return jsonify({"message": "Danh mục không tồn tại"}), 404

    #         user_id = user_result[0]

    #         # Lấy budget từ bảng USER
    #         cur.execute('SELECT budget FROM "USER" WHERE id = %s', [user_id])
    #         budget_result = cur.fetchone()
    #         if not budget_result or budget_result[0] is None:
    #             cur.close()
    #             conn.close()
    #             return jsonify({"message": "Người dùng chưa thiết lập ngân sách"}), 400

    #         budget = float(budget_result[0])

    #         # Tính toán amount mới

    #         amount = (percentage_limit / 100) * budget
    #     except Exception as e:
    #         cur.close()
    #         conn.close()
    #         return jsonify({"message": f"Lỗi khi tính toán amount: {str(e)}"}), 500
        

    # Xây dựng câu lệnh SQL động để cập nhật các trường được cung cấp
    query = 'UPDATE "CATEGORY" SET'
    params = []

    if category_type:
        query += " category_type = %s,"
        params.append(category_type)
    if category_name:
        query += " category_name = %s,"
        params.append(category_name)
    if percentage_limit is not None:
        query += " percentage_limit = %s,"
        params.append(percentage_limit)
    if amount is not None:
        query += " amount = %s,"
        params.append(amount)
    if actual_amount is not None:
        query += " actual_amount = %s,"
        params.append(actual_amount)
    if time_frame:
        query += " time_frame = %s,"
        params.append(time_frame)

    # Loại bỏ dấu phẩy cuối cùng và thêm điều kiện WHERE
    query = query.rstrip(",") + " WHERE id = %s"
    params.append(category_id)

    try:
        # Thực thi câu lệnh SQL
        cur.execute(query, params)
        conn.commit()

        if cur.rowcount == 0:
            cur.close()
            conn.close()
            return jsonify({"message": "Danh mục không tồn tại"}), 404
        
        # # Kiểm tra nếu actual_amount > amount sẽ cập nhật is_exceeded thành true
        # update_is_exceeded_query = """
        # UPDATE "CATEGORY" 
        # SET is_exceeded = CASE 
        #     WHEN actual_amount > amount THEN true
        #     ELSE false
        # END
        # WHERE id = %s
        # """
        cur.execute(query, [category_id])
        conn.commit()

        cur.close()
        conn.close()

        return jsonify({"message": "Cập nhật danh mục thành công"}), 200

    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        return jsonify({"message": f"Lỗi khi cập nhật danh mục: {str(e)}"}), 500


# Route để lấy danh mục, sắp xếp theo actual_amount
@category_bp.route("/get-categories", methods=["GET"])
def get_categories():

    category_id = request.args.get("id")
    user_id = request.args.get("user_id")
    category_type = request.args.get("category_type")
    time_frame = request.args.get("time_frame")
    is_exceeded = request.args.get("is_exceeded")
    sort_category = request.args.get("sort_category", "DESC").upper()  # Mặc định là DESC

    if not user_id:
        return jsonify({"message": "Thiếu thông tin user_id"}), 400

    # Kiểm tra giá trị của sort_category
    if sort_category not in ["ASC", "DESC"]:
        return (
            jsonify(
                {
                    "message": "Giá trị sort_category không hợp lệ, chỉ được dùng 'ASC' hoặc 'DESC'"
                }
            ),
            400,
        )

    conn = connect_db()
    cur = conn.cursor()
    # cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)  # Sử dụng RealDictCursor

    # Tạo câu truy vấn động
    query = 'SELECT * FROM "CATEGORY" WHERE user_id = %s'
    params = [user_id]

    if category_id:
        query += " AND id = %s"
        params.append(category_id)

    if category_type:
        query += " AND category_type = %s"
        params.append(category_type)

    if time_frame:
        query += " AND time_frame = %s"
        params.append(time_frame)

    if is_exceeded is not None:
        query += " AND is_exceeded = %s"
        params.append(is_exceeded)

    query += f" ORDER BY actual_amount {sort_category}"

    try:
        cur.execute(query, params)
        categories = cur.fetchall()

        cur.close()
        conn.close()

        # Chuyển kết quả thành danh sách
        categories_list = [
            {
                "id": row[0],
                "category_type": row[1],
                "category_name": row[2],
                "percentage_limit": row[3],
                "amount": row[4],
                "actual_amount": row[5],
                "is_exceeded": row[6],
                "time_frame": row[7].strftime("%d-%m-%Y"),
                "user_id": row[8],
            }
            for row in categories
        ]

        return jsonify(categories_list), 200

    except Exception as e:
        print(f"Error: {str(e)}")
        cur.close()
        conn.close()
        return jsonify({"message": f"Lỗi khi lấy danh mục: {str(e)}"}), 500


def get_category_name():
    # Lấy tham số category_id từ query string
    category_id = request.args.get("category_id")
    
    # Kiểm tra category_id
    if not category_id:
        return jsonify({"status": "error", "message": "Thiếu tham số category_id"}), 400

    # Kết nối đến cơ sở dữ liệu
    conn = connect_db()
    cur = conn.cursor()

    # Câu lệnh SQL
    query = 'SELECT category_name FROM "CATEGORY" WHERE id = %s'

    try:
        # Thực thi câu truy vấn
        cur.execute(query, [category_id])
        result = cur.fetchone()

        # Kiểm tra kết quả
        if not result:
            cur.close()
            conn.close()
            return jsonify({"status": "error", "message": "Không tìm thấy danh mục"}), 404

        category_name = result[0]

        # Đóng kết nối
        cur.close()
        conn.close()

        return jsonify({"status": "success", "category_name": category_name}), 200

    except Exception as e:
        cur.close()
        conn.close()
        return jsonify({"status": "error", "message": f"Lỗi khi truy vấn: {str(e)}"}), 500


# Route để xóa danh mục
@category_bp.route("/delete-category/<int:category_id>", methods=["DELETE"])
def delete_category(category_id):
    conn = connect_db()
    cur = conn.cursor()

    try:
        # Xóa danh mục dựa trên category_id
        cur.execute('DELETE FROM "CATEGORY" WHERE id = %s', (category_id,))
        conn.commit()

        if cur.rowcount == 0:
            cur.close()
            conn.close()
            return jsonify({"message": "Danh mục không tồn tại"}), 404

        cur.close()
        conn.close()

        return jsonify({"message": "Xóa danh mục thành công"}), 200

    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        return jsonify({"message": f"Lỗi khi xóa danh mục: {str(e)}"}), 500
