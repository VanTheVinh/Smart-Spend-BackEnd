import jwt
import bcrypt
import os
import base64
import requests
from werkzeug.utils import secure_filename
from flask import Blueprint, request, jsonify, make_response
from datetime import datetime, timedelta, timezone
from modules.db import connect_db
from datetime import datetime, timedelta


API_URL_DEPLOYED = "https://smart-spend-backend-production.up.railway.app"
API_URL_LOCAL = "http://127.0.0.1:5000"


# Tạo blueprint cho các route liên quan đến đăng nhập
auth_bp = Blueprint("auth", __name__)
SECRET_KEY = "your_secret_key_here"  # Khóa bí mật dùng để ký JWT


# Cấu hình GitHub API
GITHUB_API_URL = (
    "https://api.github.com/repos/VanTheVinh/avatars-storage-spend-web/contents"
)
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")  # Token GitHub từ biến môi trường

# Hỗ trợ định dạng file hợp lệ
ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg"}


def allowed_file(filename):
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


@auth_bp.route("/upload-avatar/<int:user_id>", methods=["POST"])
def upload_avatar(user_id):
    """
    Endpoint để người dùng tải lên avatar và lưu vào GitHub repo với tên file avatar_user_<user_id>.
    """
    try:
        # Kiểm tra xem request có chứa file không
        if "avatar" not in request.files:
            return jsonify({"status": "error", "message": "Không có file avatar"}), 400

        file = request.files["avatar"]

        # Kiểm tra nếu file trống
        if file.filename == "":
            return (
                jsonify(
                    {"status": "error", "message": "Không có file avatar được chọn"}
                ),
                400,
            )

        # Kiểm tra định dạng file
        if file and allowed_file(file.filename):
            # Đổi tên file thành avatar_user_<user_id> với đúng phần mở rộng
            file_extension = file.filename.rsplit(".", 1)[1].lower()
            filename = f"avatar_user_{user_id}.{file_extension}"

            # Kiểm tra xem file cũ đã tồn tại trên GitHub hay chưa
            response_check = requests.get(
                f"{GITHUB_API_URL}/avatars/{filename}",
                headers={
                    "Authorization": f"token {GITHUB_TOKEN}",
                    "Accept": "application/vnd.github.v3+json",
                },
            )

            sha = None
            if response_check.status_code == 200:
                # Lấy SHA của file hiện tại nếu tồn tại
                sha = response_check.json().get("sha")

            # Đọc nội dung file và encode thành base64
            file_content = file.read()
            encoded_content = base64.b64encode(file_content).decode("utf-8")

            # Tạo payload để upload hoặc thay thế file trên GitHub
            payload = {
                "message": f"Upload avatar for user {user_id}",
                "content": encoded_content,
                "committer": {"name": "Your Name", "email": "your_email@example.com"},
            }

            if sha:
                payload["sha"] = sha  # Thêm SHA nếu file đã tồn tại để thay thế

            # Gửi request để upload file lên GitHub
            response = requests.put(
                f"{GITHUB_API_URL}/avatars/{filename}",
                headers={
                    "Authorization": f"token {GITHUB_TOKEN}",
                    "Accept": "application/vnd.github.v3+json",
                },
                json=payload,
            )

            # Kiểm tra phản hồi từ GitHub API
            if response.status_code in (200, 201):  # 200: Update, 201: Create
                avatar_url = response.json()["content"]["download_url"]

                # Cập nhật đường dẫn avatar trong cơ sở dữ liệu
                with connect_db() as conn:
                    with conn.cursor() as cur:
                        cur.execute('SELECT id FROM "USER" WHERE id = %s', (user_id,))
                        user = cur.fetchone()

                        if not user:
                            return (
                                jsonify(
                                    {
                                        "status": "error",
                                        "message": "Người dùng không tồn tại",
                                    }
                                ),
                                404,
                            )

                        # Cập nhật avatar trong cơ sở dữ liệu
                        cur.execute(
                            'UPDATE "USER" SET avatar = %s WHERE id = %s',
                            (avatar_url, user_id),
                        )
                        conn.commit()

                return (
                    jsonify(
                        {
                            "status": "success",
                            "message": "Avatar đã được cập nhật thành công",
                            "avatar": avatar_url,
                        }
                    ),
                    200,
                )

            else:
                # Lấy chi tiết lỗi từ phản hồi của GitHub
                error_details = response.json()
                return (
                    jsonify(
                        {
                            "status": "error",
                            "message": "Không thể tải ảnh lên GitHub",
                            "details": error_details,
                        }
                    ),
                    500,
                )

        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Định dạng file không hợp lệ. Chỉ hỗ trợ file .png, .jpg, .jpeg",
                }
            ),
            400,
        )

    except Exception as e:
        # Xử lý lỗi chung
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Đã xảy ra lỗi khi tải lên avatar",
                    "details": str(e),
                }
            ),
            500,
        )


@auth_bp.route("/delete-avatar/<int:user_id>", methods=["DELETE"])
def delete_avatar(user_id):
    """
    Endpoint để xóa avatar của người dùng khỏi GitHub repo.
    """
    try:
        with connect_db() as conn:
            with conn.cursor() as cur:
                # Lấy thông tin avatar từ database
                cur.execute('SELECT avatar FROM "USER" WHERE id = %s', (user_id,))
                user = cur.fetchone()

                if not user or not user[0]:
                    return (
                        jsonify(
                            {
                                "status": "error",
                                "message": "Người dùng không tồn tại hoặc không có avatar",
                            }
                        ),
                        404,
                    )

                avatar_url = user[0]

                # Lấy tên file từ URL avatar
                filename = avatar_url.split("/")[-1]

                # API URL đến file trên GitHub
                github_file_url = f"{GITHUB_API_URL}/avatars/{filename}"

                # Lấy thông tin sha của file
                sha_response = requests.get(
                    github_file_url,
                    headers={
                        "Authorization": f"token {GITHUB_TOKEN}",
                        "Accept": "application/vnd.github.v3+json",
                    },
                )

                if sha_response.status_code != 200:
                    return (
                        jsonify(
                            {
                                "status": "error",
                                "message": "Không tìm thấy file trên GitHub",
                            }
                        ),
                        404,
                    )

                file_sha = sha_response.json()["sha"]

                # Xóa file bằng GitHub API
                delete_payload = {
                    "message": f"Delete avatar for user {user_id}",
                    "sha": file_sha,
                    "committer": {
                        "name": "Your Name",
                        "email": "your_email@example.com",
                    },
                }

                delete_response = requests.delete(
                    github_file_url,
                    headers={
                        "Authorization": f"token {GITHUB_TOKEN}",
                        "Accept": "application/vnd.github.v3+json",
                    },
                    json=delete_payload,
                )

                if delete_response.status_code == 200:
                    # Xóa đường dẫn avatar trong cơ sở dữ liệu
                    cur.execute(
                        'UPDATE "USER" SET avatar = NULL WHERE id = %s', (user_id,)
                    )
                    conn.commit()

                    return (
                        jsonify(
                            {
                                "status": "success",
                                "message": "Avatar đã được xóa thành công",
                            }
                        ),
                        200,
                    )

                else:
                    return (
                        jsonify(
                            {
                                "status": "error",
                                "message": "Không thể xóa avatar khỏi GitHub",
                                "details": delete_response.json(),
                            }
                        ),
                        500,
                    )

    except Exception as e:
        return (
            jsonify(
                {
                    "status": "error",
                    "message": "Đã xảy ra lỗi khi xóa avatar",
                    "details": str(e),
                }
            ),
            500,
        )


# Hàm tạo Access Token
def generate_access_token(user_id):
    expiration = datetime.now(timezone.utc) + timedelta(hours=1)
    # Token có hiệu lực trong 1 giờ
    payload = {"user_id": user_id, "exp": expiration}
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


def generate_refresh_token(user_id):
    expiration = datetime.now(timezone.utc) + timedelta(
        days=7
    )  # Refresh token có thể có hiệu lực 7 ngày
    # Refresh token có thể dùng để tạo access token mới
    payload = {
        "user_id": user_id,
        "exp": expiration,  # Chỉ có thể dùng refresh token trong một khoảng thời gian dài
    }
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")


# Middleware kiểm tra Access Token
def token_required(func):
    def wrapper(*args, **kwargs):
        # Lấy token từ cookie thay vì header
        token = request.cookies.get("access_token")

        if not token:
            return jsonify({"message": "Access Token không hợp lệ"}), 401

        try:
            decoded_token = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            request.user_id = decoded_token["user_id"]
        except jwt.ExpiredSignatureError:
            print("Lỗi: Token đã hết hạn")
            return jsonify({"message": "Token đã hết hạn"}), 401
        except jwt.InvalidTokenError as e:
            print(f"Lỗi: Token không hợp lệ - {e}")
            return jsonify({"message": "Token không hợp lệ"}), 401

        return func(*args, **kwargs)

    wrapper.__name__ = func.__name__
    return wrapper


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")
    fullname = data.get("fullname")
    email = data.get("email")
    avatar = data.get("avatar")  # Tùy chọn, có thể không có

    if not username:
        return jsonify({"message": "Vui lòng nhập tên người dùng"}), 400
    if not password:
        return jsonify({"message": "Vui lòng nhập mật khẩu"}), 400
    if not fullname:
        return jsonify({"message": "Vui lòng nhập tên đầy đủ"}), 400
    if not email:
        return jsonify({"message": "Vui lòng nhập email"}), 400

    conn = connect_db()
    cur = conn.cursor()

    # Kiểm tra tên người dùng đã tồn tại
    cur.execute('SELECT * FROM "USER" WHERE username = %s', (username,))
    existing_user = cur.fetchone()

    if existing_user:
        cur.close()
        conn.close()
        return jsonify({"message": "Tên người dùng đã tồn tại"}), 409

    # Kiểm tra email đã tồn tại
    cur.execute('SELECT 1 FROM "USER" WHERE email = %s', (email,))
    existing_email = cur.fetchone()

    if existing_email:
        cur.close()
        conn.close()
        return jsonify({"message": "Email đã được đăng ký"}), 409

    # Mã hóa mật khẩu
    hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode(
        "utf-8"
    )

    # Ngày hiện tại (ngày đăng ký)
    today_date = datetime.now().strftime("%Y-%m-%d")

    # Thêm người dùng mới
    cur.execute(
        'INSERT INTO "USER" (username, password, fullname, email, avatar) VALUES (%s, %s, %s, %s, %s) RETURNING id',
        (username, hashed_password, fullname, email, avatar),
    )
    user_id = cur.fetchone()[0]
    conn.commit()

    # Thêm các danh mục mặc định
    DEFAULT_CATEGORIES = [
        {"category_name": "Lương", "category_type": "THU"},
        {"category_name": "Thu nhập khác", "category_type": "THU"},
        {"category_name": "Tiền chuyển đến", "category_type": "THU"},
        {"category_name": "Ăn uống", "category_type": "CHI"},
        {"category_name": "Di chuyển", "category_type": "CHI"},
        {
            "category_name": "Tiện ích (Thuê nhà, điện, nước, wifi, internet, ...)",
            "category_type": "CHI",
        },
        {"category_name": "Giải trí", "category_type": "CHI"},
        {"category_name": "Khác", "category_type": "CHI"},
    ]

    try:
        for category in DEFAULT_CATEGORIES:
            # Kiểm tra amount và actual_amount, gán giá trị mặc định nếu cần
            percentage_limit = category.get("percentage_limit", 0) or 0
            amount = category.get("amount", 0) or 0
            actual_amount = category.get("actual_amount", 0) or 0

            cur.execute(
                """
                INSERT INTO "CATEGORY" (user_id, category_name, category_type, percentage_limit, amount, actual_amount, time_frame)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    user_id,
                    category["category_name"],
                    category["category_type"],
                    percentage_limit,
                    amount,
                    actual_amount,
                    today_date,
                ),
            )
        conn.commit()
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        return jsonify({"message": f"Lỗi khi thêm danh mục mặc định: {str(e)}"}), 500

    cur.close()
    conn.close()
    return jsonify({"message": "Đăng ký thành công"}), 201


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json()
    username = data.get("username")
    password = data.get("password")

    if not username:
        return jsonify({"message": "Thiếu tên người dùng"}), 400
    if not password:
        return jsonify({"message": "Thiếu mật khẩu"}), 400

    conn = connect_db()
    cur = conn.cursor()
    cur.execute(
        'SELECT id, username, fullname, avatar, password, budget FROM "USER" WHERE username = %s',
        (username,),
    )
    user = cur.fetchone()
    cur.close()
    conn.close()

    if user:
        user_id, stored_username, fullname, avatar, stored_password, budget = user

        try:
            # Kiểm tra mật khẩu
            if bcrypt.checkpw(
                password.encode("utf-8"), stored_password.encode("utf-8")
            ):
                # Tạo Access Token và Refresh Token
                access_token = generate_access_token(user_id)
                refresh_token = generate_refresh_token(user_id)  # Tạo refresh token

                # Trả về thông tin người dùng và token
                return (
                    jsonify(
                        {
                            "message": "Đăng nhập thành công",
                            "user_info": {
                                "user_id": user_id,
                                "username": stored_username,
                                "fullname": fullname,
                                "avatar": avatar,
                                "budget": budget,
                            },
                            "access_token": access_token,  # Trả về access_token
                            "refresh_token": refresh_token,  # Trả về refresh_token
                        }
                    ),
                    200,
                )
            else:
                return (
                    jsonify({"message": "Tên người dùng hoặc mật khẩu không đúng"}),
                    401,
                )
        except ValueError as e:
            print(f"Lỗi giải mã mật khẩu: {e}")
            return (
                jsonify({"message": "Mật khẩu trong cơ sở dữ liệu không hợp lệ"}),
                500,
            )
    else:
        return jsonify({"message": "Người dùng không tồn tại"}), 404


# Đăng xuất
@auth_bp.route("/logout", methods=["POST"])
def logout():
    response = make_response(jsonify({"message": "Đăng xuất thành công"}), 200)
    response.delete_cookie("access_token")  # Xóa cookie chứa token
    return response


# Kiểm tra phiên đăng nhập
@auth_bp.route("/protected", methods=["GET"])
@token_required
def protected():
    return (
        jsonify({"message": f"Phiên đăng nhập hợp lệ cho user_id: {request.user_id}"}),
        200,
    )


@auth_bp.route("/get-user/<int:user_id>", methods=["GET"])
def get_user(user_id):
    """
    Endpoint để lấy tất cả thông tin của người dùng dựa trên user_id.
    """
    try:
        # Kết nối đến cơ sở dữ liệu
        with connect_db() as conn:
            with conn.cursor() as cur:
                # Truy vấn tất cả thông tin người dùng từ bảng USER
                cur.execute(
                    'SELECT id, username, fullname, avatar, budget, actual_budget FROM "USER" WHERE id = %s',
                    (user_id,),
                )
                user = cur.fetchone()

                # Kiểm tra xem người dùng có tồn tại
                if not user:
                    return (
                        jsonify(
                            {"status": "error", "message": "Người dùng không tồn tại"}
                        ),
                        404,
                    )

                # Định dạng thông tin người dùng thành dictionary
                user_info = {
                    "id": user[0],
                    "username": user[1],
                    "fullname": user[2],
                    "avatar": user[3],
                    "budget": user[4],
                    "actual_budget": user[5],
                }

                # Trả về thông tin người dùng trực tiếp mà không bọc trong "user"
                return jsonify(user_info), 200
    except Exception as e:
        # Xử lý lỗi và trả về thông báo lỗi
        return (
            jsonify(
                {"status": "error", "message": "Đã xảy ra lỗi trong quá trình xử lý"}
            ),
            500,
        )


@auth_bp.route("/update-user/<int:user_id>", methods=["PUT"])
def update_user(user_id):
    """
    Endpoint để cập nhật tất cả thông tin của người dùng dựa trên user_id, bao gồm mật khẩu.
    """
    try:
        # Lấy dữ liệu từ request
        data = request.json

        # Kiểm tra xem các trường cần thiết có trong dữ liệu không
        username = data.get("username")
        fullname = data.get("fullname")
        avatar = data.get("avatar")
        budget = data.get("budget")
        password = data.get("password")  # Lấy mật khẩu từ request

        # Chuyển user_id và budget thành kiểu số nguyên
        user_id = int(user_id)  # Đảm bảo user_id là số nguyên
        if budget is not None:
            budget = int(budget)  # Đảm bảo budget là số nguyên nếu có

        # Kết nối đến cơ sở dữ liệu
        with connect_db() as conn:
            with conn.cursor() as cur:
                # Truy vấn kiểm tra người dùng có tồn tại không
                cur.execute('SELECT id FROM "USER" WHERE id = %s', (user_id,))
                user = cur.fetchone()

                if not user:
                    return (
                        jsonify(
                            {"status": "error", "message": "Người dùng không tồn tại"}
                        ),
                        404,
                    )

                # Cập nhật thông tin người dùng
                update_fields = []
                update_values = []

                if username:
                    update_fields.append("username = %s")
                    update_values.append(username)

                if fullname:
                    update_fields.append("fullname = %s")
                    update_values.append(fullname)

                if avatar is not None:  # cho phép giá trị avatar là null
                    update_fields.append("avatar = %s")
                    update_values.append(avatar)

                if budget is not None:  # cho phép giá trị budget là null
                    update_fields.append("budget = %s")
                    update_values.append(budget)

                if password:  # Nếu có mật khẩu mới
                    # Mã hóa mật khẩu mới
                    hashed_password = bcrypt.hashpw(
                        password.encode("utf-8"), bcrypt.gensalt()
                    ).decode("utf-8")
                    update_fields.append("password = %s")
                    update_values.append(hashed_password)

                if not update_fields:
                    return (
                        jsonify(
                            {
                                "status": "error",
                                "message": "Không có thông tin nào để cập nhật",
                            }
                        ),
                        400,
                    )

                # Thêm điều kiện để cập nhật cho người dùng cụ thể
                update_values.append(user_id)
                update_query = (
                    f'UPDATE "USER" SET {", ".join(update_fields)} WHERE id = %s'
                )
                cur.execute(update_query, tuple(update_values))
                conn.commit()

                # Trả về thông báo thành công
                return (
                    jsonify(
                        {
                            "status": "success",
                            "message": "Thông tin người dùng đã được cập nhật thành công",
                        }
                    ),
                    200,
                )

    except Exception as e:
        # Xử lý lỗi và trả về thông báo lỗi
        return (
            jsonify(
                {"status": "error", "message": "Đã xảy ra lỗi trong quá trình xử lý"}
            ),
            500,
        )


# Xóa người dùng
@auth_bp.route("/delete-user/<int:user_id>", methods=["DELETE"])
# @token_required
def delete_user(user_id):
    conn = connect_db()
    cur = conn.cursor()

    try:
        # Kiểm tra xem người dùng có tồn tại không
        cur.execute('SELECT id FROM "USER" WHERE id = %s', (user_id,))
        user = cur.fetchone()

        if not user:
            cur.close()
            conn.close()
            return jsonify({"message": "Người dùng không tồn tại"}), 404

        # Xóa người dùng
        cur.execute('DELETE FROM "USER" WHERE id = %s', (user_id,))
        conn.commit()
        cur.close()
        conn.close()

        return jsonify({"message": "Xóa người dùng thành công"}), 200
    except Exception as e:
        conn.rollback()
        cur.close()
        conn.close()
        return jsonify({"message": f"Lỗi khi xóa người dùng: {str(e)}"}), 500


# Hàm gửi email đặt lại mật khẩu
