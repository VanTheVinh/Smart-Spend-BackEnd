from flask import Blueprint, request, jsonify
from modules.db import connect_db

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("/get-dashboard-overview", methods=["GET"])
def get_dashboard_overview():
    # Lấy tham số từ query string
    user_id = request.args.get("user_id")

    # Kiểm tra tham số bắt buộc
    if not user_id:
        return jsonify({"message": "Tham số user_id là bắt buộc"}), 400

    try:
        user_id = int(user_id)
    except ValueError:
        return jsonify({"message": "Tham số user_id phải là số nguyên"}), 400

    # Kết nối đến cơ sở dữ liệu
    conn = connect_db()
    cur = conn.cursor()

    try:
        # 1. Lấy tổng thu nhập và tổng chi tiêu
        income_query = """
            SELECT COALESCE(SUM(amount), 0)
            FROM "BILL"
            WHERE user_id = %s AND type = 'THU' AND is_group_bill = false
        """
        expense_query = """
            SELECT COALESCE(SUM(amount), 0)
            FROM "BILL"
            WHERE user_id = %s AND type = 'CHI' AND is_group_bill = false
        """

        cur.execute(income_query, (user_id,))
        total_income = cur.fetchone()[0]

        cur.execute(expense_query, (user_id,))
        total_expense = cur.fetchone()[0]

        # 2. Lấy danh sách danh mục chi tiêu với trạng thái vượt ngân sách
        exceeded_query = """
            SELECT category_name, actual_amount, amount
            FROM "CATEGORY"
            WHERE user_id = %s AND is_exceeded = true
        """

        cur.execute(exceeded_query, (user_id,))
        exceeded_categories = cur.fetchall()

        exceeded_categories_list = [
            {
                "category_name": row[0],
                "actual_amount": row[1],
                "budget": row[2]
            }
            for row in exceeded_categories
        ]

        # 3. Tổng hợp dữ liệu trả về
        overview_data = {
            "total_income": total_income,
            "total_expense": total_expense,
            "balance": total_income - total_expense,
            "exceeded_categories": exceeded_categories_list
        }

        cur.close()
        conn.close()

        return jsonify({"status": "success", "data": overview_data}), 200

    except Exception as e:
        cur.close()
        conn.close()
        return jsonify({"message": f"Lỗi khi lấy dữ liệu: {str(e)}"}), 500
