from flask import Blueprint, request, jsonify
from modules.db import connect_db
import pandas as pd
import os

invoice_process_bp = Blueprint("invoice_process", __name__)


# Route để tải lên file Excel và xử lý dữ liệu
@invoice_process_bp.route("/upload-invoice", methods=["POST"])
def upload_invoice():
    if "file" not in request.files:
        return jsonify({"message": "No file attached"}), 400

    file = request.files["file"]

    if file.filename == "":
        return jsonify({"message": "File name is empty"}), 400

    if file and file.filename.endswith(".xlsx"):
        file_path = os.path.join("uploads", file.filename)
        file.save(file_path)

        # Đọc dữ liệu từ file Excel
        try:
            data = pd.read_excel(file_path)
        except Exception as e:
            return jsonify({"message": f"Error reading file: {str(e)}"}), 500

        conn = connect_db()
        cur = conn.cursor()

        for _, row in data.iterrows():
            try:
                # Giả sử dữ liệu từ file Excel có các cột tương ứng
                bill_type = row["type"] 
                is_income = row["source"]  
                amount = row["amount"]
                date = row["date"]
                description = row["description"]
                user_id = row["user_id"]
                category_id = row["category_id"]

                cur.execute(
                    'INSERT INTO "BILL" (type, source, amount, date, description, user_id, category_id) VALUES (%s, %s, %s, %s, %s, %s, %s)',
                    (
                        bill_type,
                        is_income,
                        amount,
                        date,
                        description,
                        user_id,
                        category_id,
                    ),
                )
            except Exception as e:
                conn.rollback()
                cur.close()
                conn.close()
                return jsonify({"message": f"Error inserting data: {str(e)}"}), 500

        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"message": "Data processed successfully"}), 200
    else:
        return jsonify({"message": "Invalid file format"}), 400


# Route để nhập hóa đơn thủ công
@invoice_process_bp.route("/manual-entry", methods=["POST"])
def manual_entry():
    data = request.get_json()

    # Lấy ra các trường tương tự như file Excel
    bill_type = data.get("type")
    is_income = data.get("source")
    amount = data.get("amount")
    date = data.get("date")
    description = data.get("description")
    user_id = data.get("user_id")
    category_id = data.get("category_id")

    # Kiểm tra các trường bắt buộc
    if not bill_type or not is_income or not amount or not date or not description or not category_id or not user_id:
        return jsonify({"message": "Thiếu thông tin bắt buộc"}), 400

    conn = connect_db()
    cur = conn.cursor()

    try:
        # Thực hiện chèn dữ liệu vào database giống như khi tải lên file Excel
        cur.execute(
            'INSERT INTO "BILL" (type, source, amount, date, description, user_id, category_id) VALUES (%s, %s, %s, %s, %s, %s, %s)',
            (bill_type, is_income, amount, date, description, user_id, category_id),
        )
        conn.commit()
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        return jsonify({"message": f"Lỗi khi thêm dữ liệu: {str(e)}"}), 500

    cur.close()
    conn.close()

    return jsonify({"message": "Nhập hóa đơn thủ công thành công"}), 201
