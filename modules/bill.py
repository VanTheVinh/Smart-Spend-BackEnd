from flask import Blueprint, request, jsonify
from datetime import datetime
from modules.db import connect_db
import pandas as pd
import os

bill_bp = Blueprint("bill", __name__)

# Route để tải lên file Excel và xử lý dữ liệu
@bill_bp.route("/upload-bill", methods=["POST"])
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
                type = row["type"] 
                is_income = row["source"]  
                amount = row["amount"]
                date = row["date"]
                description = row["description"]
                user_id = row["user_id"]
                category_id = row["category_id"]

                cur.execute(
                    'INSERT INTO "BILL" (type, source, amount, date, description, user_id, category_id) VALUES (%s, %s, %s, %s, %s, %s, %s)',
                    (
                        type,
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
@bill_bp.route("/manual-bill", methods=["POST"])
def manual_entry():
    data = request.get_json()

    # Kiểm tra các trường bắt buộc
    if not all([data.get("type"), data.get("source"), data.get("amount"), data.get("date"), data.get("user_id"), data.get("category_id")]):
        return jsonify({"message": "Thiếu thông tin bắt buộc"}), 400

    # Kiểm tra giá trị của type
    bill_type = data.get("type")
    if bill_type not in ["CHI", "THU"]:
        return jsonify({"message": "Giá trị của 'type' phải là 'CHI' hoặc 'THU'"}), 400

    # Kiểm tra giá trị của source
    source = data.get("source")
    if source not in ["TIỀN MẶT", "CHUYỂN KHOẢN"]:
        return jsonify({"message": "Giá trị của 'source' phải là 'TIỀN MẶT' hoặc 'CHUYỂN KHOẢN'"}), 400

    # Kiểm tra định dạng ngày
    try:
        date = datetime.strptime(data.get("date"), "%Y-%m-%d")
    except ValueError:
        return jsonify({"message": "Ngày không hợp lệ"}), 400

    # Kiểm tra số tiền
    try:
        amount = float(data.get("amount"))
        if amount < 0:
            return jsonify({"message": "Số tiền không thể âm"}), 400
    except ValueError:
        return jsonify({"message": "Số tiền không hợp lệ"}), 400

    # Xử lý dữ liệu
    type = data.get("type")
    is_income = data.get("source")
    amount = data.get("amount")
    date = data.get("date")
    description = data.get("description")
    user_id = data.get("user_id")
    category_id = data.get("category_id")

    conn = connect_db()
    cur = conn.cursor()

    try:
        # Kiểm tra xem category_id có tồn tại trong bảng CATEGORY không
        cur.execute('SELECT * FROM "CATEGORY" WHERE id = %s', (category_id,))
        category_exists = cur.fetchone()
        if not category_exists:
            cur.close()
            conn.close()
            return jsonify({"message": "Category_id không tồn tại"}), 400

        # Chèn dữ liệu vào database 
        cur.execute(
            'INSERT INTO "BILL" (type, source, amount, date, description, user_id, category_id) VALUES (%s, %s, %s, %s, %s, %s, %s)',
            (type, is_income, amount, date, description, user_id, category_id),
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


# Route để lấy thông tin hóa đơn
@bill_bp.route("/get-bills", methods=["GET"])
def get_bills():
    # Lấy tham số từ query string
    bill_type = request.args.get("type")
    source = request.args.get("source")
    date = request.args.get("date")
    user_id = request.args.get("user_id")
    category_id = request.args.get("category_id")
    month = request.args.get("month")
    year = request.args.get("year")

    # Kết nối đến cơ sở dữ liệu
    conn = connect_db()
    cur = conn.cursor()

    # Xây dựng câu lệnh SQL
    query = 'SELECT * FROM "BILL" WHERE 1=1'  # 1=1 là để tiện nối thêm điều kiện sau này
    params = []

    # Thêm các điều kiện vào câu truy vấn
    if bill_type:
        query += ' AND type = %s'
        params.append(bill_type)
    if source:
        query += ' AND source = %s'
        params.append(source)
    if date:
        query += ' AND date = %s'
        params.append(date)
    if user_id:
        query += ' AND user_id = %s'
        params.append(user_id)
    if category_id:
        query += ' AND category_id = %s'
        params.append(category_id)

    # Kiểm tra và thêm điều kiện theo tháng và năm nếu có
    if month and year:
        try:
            month = int(month)
            year = int(year)
        except ValueError:
            cur.close()
            conn.close()
            return jsonify({"message": "Tham số month và year phải là số nguyên"}), 400
        
        if month < 1 or month > 12:
            cur.close()
            conn.close()
            return jsonify({"message": "Tháng không hợp lệ, phải trong khoảng từ 1 đến 12"}), 400
        
        query += '''
        AND EXTRACT(MONTH FROM date) = %s 
        AND EXTRACT(YEAR FROM date) = %s
        '''
        params.extend([month, year])

    try:
        # Thực thi câu lệnh SQL
        cur.execute(query, params)
        bills = cur.fetchall()

        # Chuyển đổi kết quả truy vấn thành danh sách từ điển
        bills_list = []
        for bill in bills:
            bills_list.append({
                "id": bill[0],
                "type": bill[1],
                "source": bill[2],
                "amount": bill[3],
                "date": bill[4],
                "description": bill[5],
                "user_id": bill[6],
                "category_id": bill[7]
            })

        cur.close()
        conn.close()

        return jsonify(bills_list), 200

    except Exception as e:
        cur.close()
        conn.close()
        return jsonify({"message": f"Lỗi khi lấy dữ liệu: {str(e)}"}), 500


# Cập nhật bill theo id
@bill_bp.route("/update-bill/<int:bill_id>", methods=["PUT"])
def update_bill(bill_id):
    data = request.get_json()

    # Lấy ra các trường cần cập nhật
    bill_type = data.get("type")
    source = data.get("source")
    amount = data.get("amount")
    date = data.get("date")
    description = data.get("description")
    category_id = data.get("category_id")

    if not any([bill_type, source, amount, date, description, category_id]):
        return jsonify({"message": "Không có thông tin để cập nhật"}), 400

    conn = connect_db()
    cur = conn.cursor()

    # Kiểm tra xem hóa đơn có tồn tại hay không
    cur.execute('SELECT * FROM "BILL" WHERE id = %s', (bill_id,))
    existing_bill = cur.fetchone()
    if not existing_bill:
        cur.close()
        conn.close()
        return jsonify({"message": "Hóa đơn không tồn tại"}), 404

    # Kiểm tra tính hợp lệ của dữ liệu
    if date:
        try:
            # Giả sử bạn sử dụng định dạng YYYY-MM-DD
            datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            cur.close()
            conn.close()
            return jsonify({"message": "Ngày không hợp lệ, định dạng đúng là YYYY-MM-DD"}), 400

    # Xây dựng câu lệnh SQL động để cập nhật các trường được cung cấp
    query = 'UPDATE "BILL" SET'
    params = []

    if bill_type:
        query += ' type = %s,'
        params.append(bill_type)
    if source:
        query += ' source = %s,'
        params.append(source)
    if amount:
        query += ' amount = %s,'
        params.append(amount)
    if date:
        query += ' date = %s,'
        params.append(date)
    if description:
        query += ' description = %s,'
        params.append(description)
    if category_id:
        query += ' category_id = %s,'
        params.append(category_id)

    # Loại bỏ dấu phẩy cuối cùng và thêm điều kiện WHERE
    query = query.rstrip(',') + ' WHERE id = %s'
    params.append(bill_id)

    try:
        # Thực thi câu lệnh SQL
        cur.execute(query, params)
        conn.commit()

        if cur.rowcount == 0:
            cur.close()
            conn.close()
            return jsonify({"message": "Hóa đơn không tồn tại"}), 404

        cur.close()
        conn.close()

        return jsonify({"message": "Cập nhật hóa đơn thành công"}), 200

    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        return jsonify({"message": f"Lỗi khi cập nhật dữ liệu: {str(e)}"}), 500


# Xóa bill theo id
@bill_bp.route("/delete-bill/<int:id>", methods=["DELETE"])
def delete_bill(id):
    conn = connect_db()
    cur = conn.cursor()

    try:
        # Thực hiện câu lệnh xóa hóa đơn theo ID
        cur.execute('DELETE FROM "BILL" WHERE id = %s', (id,))
        conn.commit()

        if cur.rowcount == 0:
            cur.close()
            conn.close()
            return jsonify({"message": "Hóa đơn không tồn tại"}), 404

        cur.close()
        conn.close()

        return jsonify({"message": "Xóa hóa đơn thành công"}), 200

    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        return jsonify({"message": f"Lỗi khi xóa dữ liệu: {str(e)}"}), 500
