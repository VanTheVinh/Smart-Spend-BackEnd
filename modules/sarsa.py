from flask import Blueprint, jsonify
import psycopg2
from config import Config
from datetime import datetime, timedelta
import numpy as np
import random
from decimal import Decimal

# Tạo blueprint cho SARSA
sarsa_bp = Blueprint("sarsa", __name__)


class SARSA:
    def __init__(self, actions, alpha=0.1, gamma=0.9, epsilon=0.1):
        self.actions = actions
        self.alpha = alpha
        self.gamma = gamma
        self.epsilon = epsilon 
        self.q_table = {} # Bảng Q để lưu giá trị Q

        # Tải Q-table từ cơ sở dữ liệu khi khởi tạo
        self.load_q_table()

    # Tải dữ liệu Q_TABLE từ DB
    def load_q_table(self):
        try:
            # Kết nối đến cơ sở dữ liệu
            conn = psycopg2.connect(
                database=Config.DB_NAME,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                host=Config.DB_HOST,
                port=Config.DB_PORT,
            )
            cursor = conn.cursor()

            # Thực hiện truy vấn để lấy dữ liệu từ Q_TABLE
            cursor.execute("SELECT state, action, q_value FROM Q_TABLE")
            rows = cursor.fetchall()

            for row in rows:
                state, action, q_value = row
                if state not in self.q_table:
                    self.q_table[state] = {}
                self.q_table[state][action] = q_value

            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Không thể tải Q-table: {str(e)}")

    # Lưu dữ liệu Q_TABLE
    def save_q_table(self):
        try:
            conn = psycopg2.connect(
                database=Config.DB_NAME,
                user=Config.DB_USER,
                password=Config.DB_PASSWORD,
                host=Config.DB_HOST,
                port=Config.DB_PORT,
            )
            cursor = conn.cursor()

            # Lưu Q-table
            for state, actions in self.q_table.items():
                for action, q_value in actions.items():
                    cursor.execute(
                        """
                        INSERT INTO Q_TABLE (state, action, q_value)
                        VALUES (%s, %s, %s)
                        ON CONFLICT (state, action) 
                        DO UPDATE SET q_value = GREATEST(Q_TABLE.q_value, EXCLUDED.q_value);
                        """,
                        (state, action, q_value),
                    )

            conn.commit()
            cursor.close()
            conn.close()
        except Exception as e:
            print(f"Không thể lưu Q-table: {str(e)}")

    # Lấy giá trị Q cho trạng thái và hành động nhất định.
    def get_q_value(self, state, action):
        return self.q_table.get(state, {}).get(action, 0.0)

    def update_q_value(self, state, action, reward, next_state, next_action):
        current_q = self.get_q_value(state, action)
        next_q = self.get_q_value(next_state, next_action)
        if state not in self.q_table:
            self.q_table[state] = {}
        self.q_table[state][action] = current_q + self.alpha * (
            reward + self.gamma * next_q - current_q
        )
        # Lưu Q-table mỗi khi cập nhật
        self.save_q_table()

    def choose_action(self, state):
        if np.random.rand() < self.epsilon:
            return random.choice(self.actions)
        else:
            if state in self.q_table:
                q_values = self.q_table[state]
                max_action = max(q_values, key=q_values.get)
                return max_action
            else:
                return random.choice(self.actions)


def get_category_data(user_id):
    try:
        conn = psycopg2.connect(
            database=Config.DB_NAME,
            user=Config.DB_USER,
            password=Config.DB_PASSWORD,
            host=Config.DB_HOST,
            port=Config.DB_PORT,
        )
        cursor = conn.cursor()

        query = """
        SELECT id, category_name, category_type, amount AS budget, actual_amount, percentage_limit, time_frame
        FROM "CATEGORY"
        WHERE user_id = %s;
        """
        cursor.execute(query, (user_id,))
        rows = cursor.fetchall()

        data = []
        for row in rows:
            data.append(
                {
                    "category_id": row[0],
                    "category_name": row[1],
                    "category_type": row[2],
                    "budget": row[3],
                    "actual_amount": row[4],
                    "percentage_limit": row[5],
                    "time_frame": row[6].strftime("%Y-%m-%d"),
                }
            )

        cursor.close()
        conn.close()

        return {"data": data}

    except Exception as e:
        return {
            "status": "error",
            "message": f"Kết nối đến cơ sở dữ liệu thất bại: {str(e)}",
        }


def get_week_of_month(date):
    first_day = date.replace(day=1)
    dom = date.day
    adjusted_dom = dom + first_day.weekday()
    return int(adjusted_dom / 7) + 1


def discretize_spending_ratio(spending_ratio):
    if spending_ratio < 0:
        return 0
    elif spending_ratio > 300:
        return 300
    return int((spending_ratio // 10) * 10 + 5)


def calculate_reward(spending_ratio):
    if spending_ratio > 150:
        return -2
    elif spending_ratio > 100:
        return -1
    elif 90 < spending_ratio <= 100:
        return 0
    elif 60 < spending_ratio <= 90:
        return 1
    else:
        return 2


def generate_weekly_recommendations(data, user_id):
    actions = [
        "Giảm giới hạn ngân sách",
        "không thay đổi ngân sách",  # Sẽ loại bỏ trong kết quả
        "Tăng giới hạn ngân sách",
        "Giảm chi tiêu",
        "Tăng chi tiêu",
    ]
    sarsa = SARSA(actions)

    q_table = sarsa.q_table  # Lấy Q-table từ lớp SARSA

    weekly_recommendations = {
        week: [] for week in range(1, 5)
    }  # Đảm bảo mỗi tuần có gợi ý

    for item in data:
        actual_amount = int(item["actual_amount"])
        budget = int(item["budget"])
        category_name = item["category_name"]
        category_id = item["category_id"]
        category_type = item["category_type"]

        spending_ratio = (actual_amount / budget) * 100
        state = discretize_spending_ratio(spending_ratio)
        time_frame = datetime.strptime(item["time_frame"], "%Y-%m-%d")
        week_of_time_frame = get_week_of_month(time_frame)

        # Tạo gợi ý riêng cho mỗi tuần dựa trên loại danh mục (THU/CHI)
        recommendation = None
        exceed_date = None

        # Chi tiêu
        if category_type == "CHI":
            if spending_ratio < 60:
                action = random.choice([actions[0], actions[4]])
                recommendation = f"Bạn có thể {action.lower()} cho mục '{category_name}' vì tỷ lệ chi tiêu là {spending_ratio:.2f}%."
            elif 60 <= spending_ratio < 90:
                continue  # Bỏ qua nếu không thay đổi ngân sách
            elif 90 <= spending_ratio < 150:
                action = random.choice([actions[2], actions[3]])
                recommendation = f"Bạn có thể {action.lower()} cho mục '{category_name}' vì tỷ lệ chi tiêu là {spending_ratio:.2f}%."
            else:
                action = actions[3]
                recommendation = f"Có thể {action.lower()} cho mục '{category_name}' vì tỷ lệ chi tiêu là {spending_ratio:.2f}%."

            # Cảnh báo cho chi tiêu vượt ngân sách
            alert = spending_ratio > 100
            if alert:
                exceed_date = time_frame.strftime("%d/%m/%Y")

            # Thu nhập
        elif category_type == "THU":
            if spending_ratio > 100:
                recommendation = f"Bạn nên tăng giới hạn ngân sách cho mục '{category_name}' vì tỷ lệ thu nhập là {spending_ratio:.2f}%."
        elif spending_ratio < 60:
            recommendation = f"Có thể tìm cách tăng thu nhập cho mục '{category_name}' vì tỷ lệ thu nhập là {spending_ratio:.2f}%."

            # Thu nhập không cần cảnh báo nếu vượt ngân sách
            alert = spending_ratio < 60  # Cảnh báo nếu thu nhập quá thấp
            if alert:
                exceed_date = time_frame.strftime("%d/%m/%Y")

        if recommendation or alert:
            
            weekly_recommendations[week_of_time_frame].append(
                {
                    "category_id": category_id,
                    "category_name": category_name,
                    "recommendation": recommendation,
                    "alert": alert,  # True nếu vượt ngân sách, False nếu không
                    "exceed_date": exceed_date,  # Thêm ngày vượt ngân sách nếu có
                }
            )

    # Lưu Q-table vào cơ sở dữ liệu sau khi tạo gợi ý
    sarsa.save_q_table()

    return {
        "RECOMMEND: ": weekly_recommendations, 
        "Q_TABLE:": q_table
    }


@sarsa_bp.route("/get-weekly-sarsa/<int:user_id>", methods=["GET"])
def get_weekly_sarsa(user_id):
    """Lấy dữ liệu cần thiết cho thuật toán SARSA và tạo gợi ý chi tiêu theo tuần."""
    category_data = get_category_data(user_id)

    if "status" in category_data:
        return jsonify(category_data)

    recommendations = generate_weekly_recommendations(category_data["data"], user_id)

    return jsonify({"status": "success", "weekly_recommendations": recommendations})
