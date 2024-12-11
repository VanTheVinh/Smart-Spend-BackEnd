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
    group_name = data.get("group_name")
    created_by = data.get("created_by")  # ID của người tạo nhóm
    amount = data.get("amount", 0)  # Giá trị mặc định là 0 nếu không cung cấp

    if not group_name:
        return (
            jsonify({"message": "Thiếu thông tin tên nhóm."}),
            400,
        )
    if not created_by:
        return (
            jsonify({"message": "Thiếu thông tin người tạo."}),
            400,
        )

    if not amount:
        return (
            jsonify({"message": "Thiếu thông tin số tiền."}),
            400,
        )

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Kiểm tra xem người tạo có tồn tại trong hệ thống không
        cur.execute(
            """
            SELECT id, fullname FROM "USER"
            WHERE id = %s;
            """,
            (created_by,),
        )
        user_data = cur.fetchone()

        if not user_data:
            return jsonify({"message": "Người dùng không tồn tại."}), 400

        # Kiểm tra trùng lặp group_name và created_by
        cur.execute(
            """
            SELECT id FROM "GROUP"
            WHERE group_name = %s AND created_by = %s;
            """,
            (group_name, created_by),
        )
        existing_group = cur.fetchone()

        if existing_group:
            return (
                jsonify({"message": "Tên nhóm bị trùng lặp."}),
                400,
            )

        full_name = user_data[1]  # Lấy tên người dùng
        created_at = datetime.today().strftime("%Y-%m-%d")

        # Tạo nhóm mới và lấy ID của nhóm
        cur.execute(
            """
            INSERT INTO "GROUP" (group_name, amount, created_by, created_at)
            VALUES (%s, %s, %s, %s)
            RETURNING id;
            """,
            (group_name, amount, created_by, created_at),
        )

        group_id = cur.fetchone()[0]  # Lấy ID của nhóm mới tạo

        # Thêm người tạo vào GROUP_MEMBER với vai trò admin
        cur.execute(
            """
            INSERT INTO "GROUP_MEMBER" (group_id, user_id, full_name, role, status, joined_at)
            VALUES (%s, %s, %s, %s, %s, %s);
            """,
            (group_id, created_by, full_name, "admin", "active", created_at),
        )

        conn.commit()

        return jsonify({"message": "Tạo quỹ nhóm thành công."}), 200

    except Exception as e:
        return jsonify({"message": str(e)}), 500

    finally:
        cur.close()
        conn.close()


@group_fund_bp.route("/get-group", methods=["GET"])
def get_group():
    created_by = request.args.get("created_by")  # ID người tạo nhóm (nếu có)
    group_id = request.args.get("group_id")  # ID nhóm (nếu có)
    user_id = request.args.get("user_id")  # ID người dùng hiện tại (nếu có)

    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=RealDictCursor)

        # Nếu có `created_by`, kiểm tra xem người dùng có tồn tại không
        if created_by:
            cur.execute(
                """
                SELECT id FROM "USER"
                WHERE id = %s;
            """,
                (created_by,),
            )
            user_exists = cur.fetchone()
            if not user_exists:
                return jsonify({"message": "Người dùng không tồn tại."}), 400

        # Nếu có `group_id`, kiểm tra xem nhóm có tồn tại không
        if group_id:
            cur.execute(
                """
                SELECT id FROM "GROUP"
                WHERE id = %s;
            """,
                (group_id,),
            )
            group_exists = cur.fetchone()
            if not group_exists:
                return jsonify({"message": "Nhóm không tồn tại."}), 400

        # Nếu có `user_id`, lấy tất cả nhóm mà người dùng là thành viên
        if user_id:
            cur.execute(
                """
                SELECT g.id, g.name, g.created_at
                FROM "GROUP" g
                JOIN "GROUP_MEMBER" gm ON g.id = gm.group_id
                WHERE gm.user_id = %s AND gm.status = 'active';
            """,
                (user_id,),
            )
            groups = cur.fetchall()

            if not groups:
                return (
                    jsonify({"message": "Không tìm thấy nhóm cho người dùng này."}),
                    404,
                )

        else:
            # Xây dựng câu lệnh SQL động để lấy nhóm
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
    group_name = data.get("group_name")
    amount = data.get("amount")
    status = data.get("status")
    update_by = data.get("update_by")  # Sử dụng update_by thay vì created_by

    if not update_by:
        return (
            jsonify({"message": "Thiếu thông tin mã người dùng."}),
            400,
        )

    if not group_name:
        return (
            jsonify({"message": "Thiếu thông tin tên nhóm."}),
            400,
        )

    if not amount:
        return (
            jsonify({"message": "Thiếu thông tin tên số tiền."}),
            400,
        )

    if not status:
        return (
            jsonify({"message": "Thiếu thông tin trạng thái."}),
            400,
        )

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Kiểm tra xem update_by có tồn tại trong bảng "USER" không
        cur.execute(
            """
            SELECT id FROM "USER"
            WHERE id = %s;
            """,
            (update_by,),
        )
        user_exists = cur.fetchone()
        if not user_exists:
            return jsonify({"message": "Người dùng không tồn tại."}), 400

        # Kiểm tra xem nhóm có tồn tại không và người dùng có phải là người tạo nhóm không
        cur.execute(
            """
            SELECT created_by FROM "GROUP"
            WHERE id = %s;
            """,
            (group_id,),
        )
        group = cur.fetchone()
        if not group:
            return jsonify({"message": "Nhóm không tồn tại."}), 400

        # Kiểm tra xem update_by có trùng với created_by của nhóm không
        if group[0] != update_by:
            return (
                jsonify({"message": "Chỉ người tạo nhóm mới có quyền cập nhật nhóm."}),
                403,
            )

        # Cập nhật thông tin nhóm
        cur.execute(
            """
            UPDATE "GROUP"
            SET 
                group_name = COALESCE(%s, group_name),
                amount = COALESCE(%s, amount),
                status = COALESCE(%s, status)
            WHERE id = %s;
        """,
            (group_name, amount, status, group_id),
        )
        conn.commit()

        return jsonify({"message": "Nhóm đã được cập nhật."}), 200

    except Exception as e:
        return jsonify({"message": str(e)}), 500

    finally:
        cur.close()
        conn.close()


# Xóa nhóm
@group_fund_bp.route("/delete-group", methods=["DELETE"])
def delete_group():
    group_id = request.args.get("group_id")  # Lấy ID nhóm từ query parameter
    user_id = request.args.get("user_id")  # Lấy ID người tạo từ query parameter

    if not group_id:
        return jsonify({"message": "Thiếu thông tin mã nhóm."}), 404

    if not user_id:
        return jsonify({"message": "Thiếu thông tin người dùng."}), 404

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Kiểm tra nhóm có tồn tại
        cur.execute(
            """
            SELECT id FROM "GROUP"
            WHERE id = %s;
        """,
            (group_id,),
        )
        group_exists = cur.fetchone()
        if not group_exists:
            return jsonify({"message": "Nhóm không tồn tại."}), 404

        # Kiểm tra nhóm có tồn tại
        cur.execute(
            """
            SELECT id FROM "USER"
            WHERE id = %s;
        """,
            (user_id,),
        )
        group_exists = cur.fetchone()
        if not group_exists:
            return jsonify({"message": "Người dùng không tồn tại."}), 404

        # Kiểm tra nhóm có thuộc quyền quản lý
        cur.execute(
            """
            SELECT id FROM "GROUP"
            WHERE id = %s AND created_by = %s;
        """,
            (
                group_id,
                user_id,
            ),
        )
        identify_create_by = cur.fetchone()

        if not identify_create_by:
            return (
                jsonify(
                    {
                        "message": "Nhóm không thuộc quyền quản lý của bạn, không thể xóa."
                    }
                ),
                404,
            )

        # Xóa nhóm
        cur.execute(
            """
            DELETE FROM "GROUP"
            WHERE id = %s;
        """,
            (group_id,),
        )
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
    group_id = data.get("group_id")
    user_id = data.get("user_id")
    role = data.get("role", "member")  # Vai trò mặc định là 'member'
    status = data.get("status", "active")  # Trạng thái mặc định là 'active'
    member_amount = data.get("member_amount", 0)

    # Kiểm tra thông tin bắt buộc
    if not group_id:
        return jsonify({"message": "Thiếu thông tin mã nhóm."}), 400
    # Kiểm tra thông tin bắt buộc
    if not user_id:
        return jsonify({"message": "Thiếu thông tin người dùng."}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Kiểm tra xem nhóm có tồn tại không
        if group_id:
            cur.execute(
                """
                SELECT id FROM "GROUP"
                WHERE id = %s;
            """,
                (group_id,),
            )
            group_exists = cur.fetchone()
            if not group_exists:
                return jsonify({"message": "Nhóm không tồn tại"}), 400

        # Kiểm tra xem người dùng có tồn tại không
        cur.execute(
            """
            SELECT id, fullname FROM "USER"
            WHERE id = %s;
        """,
            (user_id,),
        )
        user_exists = cur.fetchone()
        if not user_exists:
            return jsonify({"message": "Người dùng không tồn tại"}), 400

        fullname = user_exists[1]

        # Kiểm tra xem người dùng đã là thành viên của nhóm chưa
        if group_id and user_id:
            cur.execute(
                """
                SELECT id FROM "GROUP_MEMBER"
                WHERE group_id = %s AND user_id = %s;
            """,
                (group_id, user_id),
            )
            member_exists = cur.fetchone()
            if member_exists:
                return jsonify({"message": "Người dùng đã là thành viên của nhóm"}), 400

        # Thêm thành viên mới vào nhóm
        joined_at = datetime.today().strftime("%Y-%m-%d")
        cur.execute(
            """
            INSERT INTO "GROUP_MEMBER" (group_id, user_id, role, status, joined_at, member_amount, full_name)
            VALUES (%s, %s, %s, %s, %s, %s, %s);
        """,
            (group_id, user_id, role, status, joined_at, member_amount, fullname),
        )
        conn.commit()

        return jsonify({"message": "Thêm người dùng vào nhóm thành công!"}), 200

    except Exception as e:
        return jsonify({"message": str(e)}), 500

    finally:
        cur.close()
        conn.close()


# Cập nhật ngân sách cho thành viên
@group_fund_bp.route("/update-member-amount", methods=["PUT"])
def update_member_amount():
    data = request.json
    group_id = data.get("group_id")
    user_id = data.get("user_id")
    member_amount = data.get("member_amount")
    update_by = data.get("update_by")  # Người thực hiện yêu cầu

    # Kiểm tra thông tin bắt buộc
    if not group_id:
        return jsonify({"message": "Thiếu thông tin mã nhóm."}), 400
    if not user_id:
        return jsonify({"message": "Thiếu thông tin người dùng."}), 400
    if not update_by:
        return (
            jsonify({"message": "Thiếu thông tin người thực hiện thao tác cập nhật."}),
            400,
        )
    if member_amount is None:  # Tránh trường hợp giá trị 0 bị bỏ qua
        return jsonify({"message": "Thiếu thông tin số tiền của thành viên."}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Kiểm tra vai trò của admin_id
        cur.execute(
            """
            SELECT role FROM "GROUP_MEMBER"
            WHERE group_id = %s AND user_id = %s;
        """,
            (group_id, update_by),
        )
        admin_role = cur.fetchone()
        if not admin_role or admin_role[0] != "admin":
            return (
                jsonify({"message": "Chỉ admin mới có quyền cập nhật thông tin"}),
                403,
            )

        # Kiểm tra xem nhóm có tồn tại không
        cur.execute(
            """
            SELECT id FROM "GROUP"
            WHERE id = %s;
        """,
            (group_id,),
        )
        group_exists = cur.fetchone()
        if not group_exists:
            return jsonify({"message": "Nhóm không tồn tại"}), 400

        # Kiểm tra xem người dùng có tồn tại trong nhóm không
        cur.execute(
            """
            SELECT id FROM "GROUP_MEMBER"
            WHERE group_id = %s AND user_id = %s;
        """,
            (group_id, user_id),
        )
        member_exists = cur.fetchone()
        if not member_exists:
            return (
                jsonify({"message": "Người dùng không phải là thành viên của nhóm"}),
                400,
            )

        # Cập nhật member_amount cho thành viên
        cur.execute(
            """
            UPDATE "GROUP_MEMBER"
            SET member_amount = %s
            WHERE group_id = %s AND user_id = %s;
        """,
            (member_amount, group_id, user_id),
        )
        conn.commit()

        return jsonify({"message": "Cập nhật số tiền thành viên thành công!"}), 200

    except Exception as e:
        return jsonify({"message": str(e)}), 500

    finally:
        cur.close()
        conn.close()


# Lấy thành viên
@group_fund_bp.route("/get-member", methods=["GET"])
def get_member():
    group_id = request.args.get("group_id")
    user_id = request.args.get("user_id")

    # Kiểm tra nếu không có bất kỳ tham số nào
    if not group_id and not user_id:
        return jsonify({"message": "Cần ít nhất một trong hai thông tin: group_id hoặc user_id."}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Xây dựng câu truy vấn động
        query = """
            SELECT user_id, full_name, role, status, joined_at, member_amount, group_id
            FROM "GROUP_MEMBER"
            WHERE 1=1
        """
        params = []

        if group_id:
            query += " AND group_id = %s"
            params.append(group_id)

        if user_id:
            query += " AND user_id = %s"
            params.append(user_id)

        # Thực thi truy vấn
        cur.execute(query, tuple(params))
        members = cur.fetchall()

        # Nếu không có thành viên nào
        if not members:
            return jsonify({"message": "Không tìm thấy thành viên nào phù hợp"}), 400

        # Trả về danh sách thành viên
        member_list = []
        for member in members:
            joined_at = member[4].strftime("%d-%m-%Y") if member[4] else None
            member_list.append(
                {
                    "user_id": member[0],
                    "full_name": member[1],
                    "role": member[2],
                    "status": member[3],
                    "joined_at": joined_at,
                    "member_amount": member[5],
                    "group_id": member[6],
                }
            )

        return jsonify({"members": member_list}), 200

    except Exception as e:
        return jsonify({"message": str(e)}), 500

    finally:
        cur.close()
        conn.close()



# Lấy chi tiết nhóm để hiển thị trong Group Details
@group_fund_bp.route("/get-group-detail", methods=["GET"])
def get_group_detail():
    group_id = request.args.get("group_id")

    if not group_id:
        return jsonify({"message": "Thiếu thông tin mã nhóm."}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Kiểm tra xem nhóm có tồn tại không
        cur.execute(
            """ 
            SELECT id, group_name, amount, status, created_by, created_at 
            FROM "GROUP"
            WHERE id = %s;
        """,
            (group_id,),
        )
        group_detail = cur.fetchone()

        if not group_detail:
            return jsonify({"message": "Nhóm không tồn tại"}), 400

        # Trả về thông tin chi tiết nhóm
        group_data = {
            "id": group_detail[0],
            "group_name": group_detail[1],
            "amount": group_detail[2],
            "status": group_detail[3],
            "created_by": group_detail[4],
            "created_at": (
                group_detail[5].strftime("%d-%m-%Y") if group_detail[5] else None
            ),
        }

        return jsonify({"group": group_data}), 200

    except Exception as e:
        return jsonify({"message": str(e)}), 500

    finally:
        cur.close()
        conn.close()


# Tìm kiếm người dùng
@group_fund_bp.route("/search-user", methods=["GET"])
def search_user():
    fullname = request.args.get("fullname")

    # Kiểm tra thông tin bắt buộc
    if not fullname:
        return jsonify({"message": "Thiếu thông tin tên đầy đủ."}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Tìm kiếm người dùng dựa trên fullname
        cur.execute(
            """
            SELECT id, username, fullname, avatar, budget
            FROM "USER"
            WHERE fullname ILIKE %s
            ORDER BY fullname ASC;
            """,
            (f"%{fullname}%",),
        )

        users = cur.fetchall()

        # Nếu không tìm thấy người dùng nào
        if not users:
            return jsonify({"message": "Không tìm thấy người dùng nào"}), 404

        # Chuẩn bị dữ liệu trả về
        user_list = []
        for user in users:
            user_list.append(
                {
                    "id": user[0],
                    "username": user[1],
                    "fullname": user[2],
                    "avatar": user[3],
                    "budget": user[4],
                }
            )

        return jsonify({"users": user_list}), 200

    except Exception as e:
        return jsonify({"message": str(e)}), 500

    finally:
        cur.close()
        conn.close()


@group_fund_bp.route("/group-spend-report", methods=["GET"])
def group_spend_report():
    # Lấy dữ liệu từ query parameters
    group_id = request.args.get("group_id")
    start_month = request.args.get("start_month")  # Tháng bắt đầu (format: YYYY-MM)
    end_month = request.args.get("end_month")  # Tháng kết thúc (format: YYYY-MM)

    # Kiểm tra thông tin bắt buộc
    if not group_id:
        return (
            jsonify({"message": "Thiếu thông tin bắt buộc: group_id"}),
            400,
        )

    # Kiểm tra định dạng tháng
    if start_month and end_month:
        try:
            start_month = datetime.strptime(start_month, "%Y-%m")
            end_month = datetime.strptime(end_month, "%Y-%m")
        except ValueError:
            return (
                jsonify(
                    {
                        "message": "Định dạng tháng không hợp lệ, vui lòng sử dụng YYYY-MM",
                    }
                ),
                400,
            )
    else:
        # Nếu không có tháng bắt đầu và kết thúc, sử dụng tháng hiện tại
        start_month = datetime.now().replace(day=1)
        end_month = datetime.now()

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Truy vấn tổng chi thu của các thành viên trong nhóm
        cur.execute(
            """
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
        """,
            (
                group_id,
                start_month.strftime("%Y-%m-%d"),
                end_month.strftime("%Y-%m-%d"),
            ),
        )

        members_report = cur.fetchall()

        if not members_report:
            return (
                jsonify(
                    {
                        "message": "Không có thông tin chi thu cho các thành viên trong nhóm",
                    }
                ),
                404,
            )

        # Đóng kết nối
        cur.close()
        conn.close()

        # Trả về báo cáo chi thu của các thành viên
        report_data = []
        for row in members_report:
            report_data.append(
                {
                    "user_id": row[0],
                    "username": row[1],
                    "total_income": float(row[2]),
                    "total_expense": float(row[3]),
                }
            )

        return jsonify({"status": "success", "data": report_data}), 200

    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# Xóa thành viên khỏi nhóm
from flask import request, jsonify


@group_fund_bp.route("/delete-member", methods=["DELETE"])
def delete_member():
    # Lấy dữ liệu từ request body
    data = request.get_json()

    group_id = data.get("group_id")
    user_id = data.get("user_id")
    deleted_by = data.get("deleted_by")

    # Kiểm tra thông tin bắt buộc
    if not group_id:
        return jsonify({"message": "Thiếu thông tin mã nhóm."}), 400

    if not user_id:
        return jsonify({"message": "Thiếu thông tin người dùng."}), 400

    if not deleted_by:
        return jsonify({"message": "Thiếu thông tin người thực hiện thao tác."}), 400

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Kiểm tra nhóm có tồn tại không
        cur.execute(
            """
            SELECT id FROM "GROUP"
            WHERE id = %s;
        """,
            (group_id,),
        )
        group_exists = cur.fetchone()
        if not group_exists:
            return jsonify({"message": "Nhóm không tồn tại"}), 404

        # Kiểm tra xem thành viên có tồn tại trong nhóm không
        cur.execute(
            """
            SELECT id FROM "GROUP_MEMBER"
            WHERE group_id = %s AND user_id = %s;
        """,
            (group_id, user_id),
        )
        member_exists = cur.fetchone()
        if not member_exists:
            return jsonify({"message": "Thành viên không tồn tại trong nhóm"}), 404

        
        # Người xóa phải là admin
        cur.execute(
            """
            SELECT id FROM "GROUP_MEMBER"
            WHERE group_id = %s AND user_id = %s AND role = 'admin';
        """,
            (group_id, deleted_by),
        )
        role_check_deleted_by = cur.fetchone()
        if not role_check_deleted_by:
            return (
                jsonify(
                    {"message": "Chỉ quản trị viên mới có thể xóa thành viên."}
                ),
                404,
            )


        # Xóa thành viên khỏi nhóm và lưu thông tin người xóa
        cur.execute(
            """
            DELETE FROM "GROUP_MEMBER"
            WHERE group_id = %s AND user_id = %s;
        """,
            (group_id, user_id),
        )

        conn.commit()

        return jsonify({"message": "Đã xóa thành viên khỏi nhóm"}), 200

    except Exception as e:
        return jsonify({"message": str(e)}), 500

    finally:
        cur.close()
        conn.close()
