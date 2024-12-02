from flask import Blueprint, jsonify, request
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime, date
from config import Config

group_fund_bp = Blueprint("group-fund", __name__)

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

@group_fund_bp.route("/create-group", methods=["POST"])
def create_group():
    data = request.json
    group_name = data.get('group_name')
    created_by = data.get('created_by')  # ID của người tạo nhóm
    amount = data.get('amount', 0)  # Giá trị mặc định là 0 nếu không cung cấp
        

    if not group_name or not created_by:
        return jsonify({"status": "error", "message": "Thiếu thông tin bắt buộc: group_name hoặc created_by"}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Nếu có `created_by`, kiểm tra xem người dùng có tồn tại không
        if created_by:
            cur.execute("""
                SELECT id FROM "USER"
                WHERE id = %s;
            """, (created_by,))
            user_exists = cur.fetchone()
            if not user_exists:
                return jsonify({"message": "Người dùng không tồn tại."}), 400

        
        created_at = datetime.today().strftime('%Y-%m-%d')

        # Tạo nhóm mới
        cur.execute("""
            INSERT INTO "GROUP" (group_name, amount, created_by, created_at)
            VALUES (%s, %s, %s, %s)
            RETURNING id;
        """, (group_name, amount, created_by, created_at))

        # group_id = cur.fetchone()[0]  # Lấy ID của nhóm mới tạo
        conn.commit()

        return jsonify({"message": "Nhóm đã được tạo"})

    except Exception as e:
        return jsonify({"message": str(e)}), 500

    finally:
        cur.close()
        conn.close()


@group_fund_bp.route("/get-group", methods=["GET"])
def get_group():
    created_by = request.args.get('created_by')  # ID người tạo nhóm (nếu có)
    group_id = request.args.get('group_id')  # ID nhóm (nếu có)

    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Nếu có `created_by`, kiểm tra xem người dùng có tồn tại không
        if created_by:
            cur.execute("""
                SELECT id FROM "USER"
                WHERE id = %s;
            """, (created_by,))
            user_exists = cur.fetchone()
            if not user_exists:
                return jsonify({"message": "Người dùng không tồn tại."}), 400

        # Nếu có `group_id`, kiểm tra xem nhóm có tồn tại không
        if group_id:
            cur.execute("""
                SELECT id FROM "GROUP"
                WHERE id = %s;
            """, (group_id,))
            group_exists = cur.fetchone()
            if not group_exists:
                return jsonify({"message": "Nhóm không tồn tại."}), 400

        # Xây dựng câu lệnh SQL động
        query = """
            SELECT * FROM "GROUP"
            WHERE 1 = 1
        """
        params = []

        # Thêm điều kiện nếu có `created_by`
        if created_by:
            query += " AND created_by = %s"
            params.append(created_by)

        # Thêm điều kiện nếu có `group_id`
        if group_id:
            query += " AND id = %s"
            params.append(group_id)

        # Thực thi truy vấn
        cur.execute(query, tuple(params))
        groups = cur.fetchall()

        if not groups:
            return jsonify({"message": "Không tìm thấy nhóm phù hợp."}), 404
        
        # Chuyển đổi ngày tháng trong kết quả trả về sang định dạng dd-mm-yyyy
        for group in groups:
            if group.get("created_at"):
                # Kiểm tra nếu là kiểu datetime.date, chuyển đổi thành chuỗi
                created_at = group["created_at"]
                if isinstance(created_at, datetime):
                    group["created_at"] = created_at.strftime("%d-%m-%Y")
                elif isinstance(created_at, date):
                    group["created_at"] = created_at.strftime("%d-%m-%Y")

        return jsonify({"groups": groups})

    except Exception as e:
        return jsonify({"message": str(e)}), 500

    finally:
        cur.close()
        conn.close()


@group_fund_bp.route("/update-group/<int:group_id>", methods=["PUT"])
def update_group(group_id):
    data = request.json
    group_name = data.get('group_name')
    amount = data.get('amount')
    status = data.get('status')
    created_by = data.get('created_by')

    if not created_by:
        return jsonify({"status": "error", "message": "Thiếu thông tin bắt buộc: created_by"}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Nếu có `created_by`, kiểm tra xem người dùng có tồn tại không
        if created_by:
            cur.execute("""
                SELECT id FROM "USER"
                WHERE id = %s;
            """, (created_by,))
            user_exists = cur.fetchone()
            if not user_exists:
                return jsonify({"message": "Người dùng không tồn tại."}), 400

        # Nếu có `group_id`, kiểm tra xem nhóm có tồn tại không
        if group_id:
            cur.execute("""
                SELECT id FROM "GROUP"
                WHERE id = %s;
            """, (group_id,))
            group_exists = cur.fetchone()
            if not group_exists:
                return jsonify({"message": "Nhóm không tồn tại."}), 400

        # Cập nhật thông tin nhóm
        cur.execute("""
            UPDATE "GROUP"
            SET 
                group_name = COALESCE(%s, group_name),
                amount = COALESCE(%s, amount),
                status = COALESCE(%s, status)
            WHERE id = %s;
        """, (group_name, amount, status, group_id))
        conn.commit()

        return jsonify({"message": "Nhóm đã được cập nhật."}), 200

    except Exception as e:
        return jsonify({"message": str(e)}), 500

    finally:
        cur.close()
        conn.close()


@group_fund_bp.route("/delete-group/<int:group_id>", methods=["DELETE"])
def delete_group(group_id):
    created_by = request.args.get('created_by')  # Lấy ID người tạo từ query parameter

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Kiểm tra nhóm có tồn tại và thuộc quyền quản lý không
        cur.execute("""
            SELECT id FROM "GROUP"
            WHERE id = %s AND created_by = %s;
        """, (group_id, created_by))
        group_exists = cur.fetchone()

        if not group_exists:
            return jsonify({"message": "Nhóm không tồn tại hoặc không thuộc quyền quản lý."}), 404

        # Xóa nhóm
        cur.execute("""
            DELETE FROM "GROUP"
            WHERE id = %s;
        """, (group_id,))
        conn.commit()

        return jsonify({"message": "Nhóm đã được xóa."})

    except Exception as e:
        return jsonify({"message": str(e)}), 500

    finally:
        cur.close()
        conn.close()

# Thêm thành viên
@group_fund_bp.route("/add-member", methods=["POST"])
def add_member():
    data = request.json
    group_id = data.get('group_id')
    user_id = data.get('user_id')
    role = data.get('role', 'member')  # Vai trò mặc định là 'member'
    status = data.get('status', 'active')  # Trạng thái mặc định là 'active'
    member_amount = data.get('member_amount', 0)

    # Kiểm tra thông tin bắt buộc
    if not group_id:
        return jsonify({"message": "Thiếu thông tin bắt buộc: group_id "}), 400
    # Kiểm tra thông tin bắt buộc
    if not user_id:
        return jsonify({"message": "Thiếu thông tin bắt buộc: user_id"}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Kiểm tra xem nhóm có tồn tại không
        if group_id:
            cur.execute("""
                SELECT id FROM "GROUP"
                WHERE id = %s;
            """, (group_id,))
            group_exists = cur.fetchone()
            if not group_exists:
                return jsonify({"message": "Nhóm không tồn tại"}), 400

        # Kiểm tra xem người dùng có tồn tại không
        if user_id:
            cur.execute("""
                SELECT id FROM "USER"
                WHERE id = %s;
            """, (user_id,))
            user_exists = cur.fetchone()
            if not user_exists:
                return jsonify({"message": "Người dùng không tồn tại"}), 400

        # Kiểm tra xem người dùng đã là thành viên của nhóm chưa
        if group_id and user_id:
            cur.execute("""
                SELECT id FROM "GROUP_MEMBER"
                WHERE group_id = %s AND user_id = %s;
            """, (group_id, user_id))
            member_exists = cur.fetchone()
            if member_exists:
                return jsonify({"message": "Người dùng đã là thành viên của nhóm"}), 400

        # Thêm thành viên mới vào nhóm
        joined_at = datetime.today().strftime('%Y-%m-%d')
        cur.execute("""
            INSERT INTO "GROUP_MEMBER" (group_id, user_id, role, status, joined_at, member_amount)
            VALUES (%s, %s, %s, %s, %s, %s);
        """, (group_id, user_id, role, status, joined_at, member_amount))
        conn.commit()

        return jsonify({"message": "Thêm người dùng vào nhóm thành công!"}), 200

    except Exception as e:
        return jsonify({"message": str(e)}), 500

    finally:
        cur.close()
        conn.close()


# Xóa thành viên khỏi nhóm
@group_fund_bp.route("/delete-member", methods=["DELETE"])
def delete_member():
    # Lấy dữ liệu từ query parameters
    group_id = request.args.get('group_id')
    user_id = request.args.get('user_id')

    # Kiểm tra thông tin bắt buộc
    if not group_id or not user_id:
        return jsonify({"status": "error", "message": "Thiếu thông tin bắt buộc: group_id hoặc user_id"}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Kiểm tra xem thành viên có tồn tại trong nhóm không
        if group_id and user_id:
            cur.execute("""
                SELECT id FROM "GROUP_MEMBER"
                WHERE group_id = %s AND user_id = %s;
            """, (group_id, user_id))
            member_exists = cur.fetchone()

            if not member_exists:
                return jsonify({"status": "error", "message": "Thành viên không tồn tại trong nhóm"}), 404

        # Xóa thành viên khỏi nhóm
        cur.execute("""
            DELETE FROM "GROUP_MEMBER"
            WHERE group_id = %s AND user_id = %s;
        """, (group_id, user_id))
        conn.commit()

        return jsonify({"message": "Đã xóa thành viên khỏi nhóm"}), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

    finally:
        cur.close()
        conn.close()

# Lấy thành viên
@group_fund_bp.route("/get-member", methods=["GET"])
def get_member():
    group_id = request.args.get('group_id')

    # Kiểm tra thông tin bắt buộc
    if not group_id:
        return jsonify({"message": "Thiếu thông tin bắt buộc: group_id"}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Kiểm tra xem nhóm có tồn tại không
        cur.execute(""" 
            SELECT id FROM "GROUP"
            WHERE id = %s;
        """, (group_id,))
        group_exists = cur.fetchone()
        if not group_exists:
            return jsonify({"message": "Nhóm không tồn tại"}), 400

        # Lấy danh sách thành viên trong nhóm
        cur.execute("""
            SELECT gm.user_id, u.username, gm.role, gm.status, gm.joined_at, gm.member_amount
            FROM "GROUP_MEMBER" gm
            JOIN "USER" u ON gm.user_id = u.id
            WHERE gm.group_id = %s;
        """, (group_id,))

        members = cur.fetchall()

        # Nếu không có thành viên nào trong nhóm
        if not members:
            return jsonify({"message": "Nhóm này không có thành viên nào"}), 400

        # Trả về danh sách thành viên
        member_list = []
        for member in members:
            member_list.append({
                "user_id": member[0],
                "username": member[1],
                "role": member[2],
                "status": member[3],
                "joined_at": member[4],
                "member_amount": member[5]
            })

        return jsonify({"members": member_list}), 200

    except Exception as e:
        return jsonify({"message": str(e)}), 500

    finally:
        cur.close()
        conn.close()


@group_fund_bp.route("/group-spend-report", methods=["GET"])
def group_spend_report():
    # Lấy dữ liệu từ query parameters
    group_id = request.args.get('group_id')
    start_month = request.args.get('start_month')  # Tháng bắt đầu (format: YYYY-MM)
    end_month = request.args.get('end_month')  # Tháng kết thúc (format: YYYY-MM)

    # Kiểm tra thông tin bắt buộc
    if not group_id:
        return jsonify({"status": "error", "message": "Thiếu thông tin bắt buộc: group_id"}), 400

    # Kiểm tra định dạng tháng
    if start_month and end_month:
        try:
            start_month = datetime.strptime(start_month, "%Y-%m")
            end_month = datetime.strptime(end_month, "%Y-%m")
        except ValueError:
            return jsonify({"status": "error", "message": "Định dạng tháng không hợp lệ, vui lòng sử dụng YYYY-MM"}), 400
    else:
        # Nếu không có tháng bắt đầu và kết thúc, sử dụng tháng hiện tại
        start_month = datetime.now().replace(day=1)
        end_month = datetime.now()

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Truy vấn tổng chi thu của các thành viên trong nhóm
        cur.execute("""
            SELECT gm.user_id, u.username,
                   COALESCE(SUM(b.amount), 0) AS total_income, 
                   COALESCE(SUM(b.expense_amount), 0) AS total_expense
            FROM "GROUP_MEMBER" gm
            JOIN "USER" u ON gm.user_id = u.id
            LEFT JOIN "BILL" b ON gm.user_id = b.user_id 
            WHERE gm.group_id = %s
              AND b.date >= %s
              AND b.date <= %s
            GROUP BY gm.user_id, u.username;
        """, (group_id, start_month.strftime("%Y-%m-%d"), end_month.strftime("%Y-%m-%d")))

        members_report = cur.fetchall()

        if not members_report:
            return jsonify({"status": "error", "message": "Không có thông tin chi thu cho các thành viên trong nhóm"}), 404

        # Đóng kết nối
        cur.close()
        conn.close()

        # Trả về báo cáo chi thu của các thành viên
        report_data = []
        for row in members_report:
            report_data.append({
                "user_id": row[0],
                "username": row[1],
                "total_income": float(row[2]),
                "total_expense": float(row[3])
            })

        return jsonify({"status": "success", "data": report_data}), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

