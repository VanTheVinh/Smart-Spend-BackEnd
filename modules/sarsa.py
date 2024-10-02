from flask import Blueprint, jsonify
import psycopg2
from config import Config
import numpy as np
import random

# Tạo blueprint cho SARSA
sarsa_bp = Blueprint("sarsa", __name__)


class SARSA:
    def __init__(self, actions, alpha=0.1, gamma=0.9, epsilon=0.1):
        self.actions = actions
        self.alpha = alpha
        self.gamma = gamma
        self.epsilon = epsilon
        self.q_table = {}  # Khởi tạo Q-table

    def get_q_value(self, state, action):
        """Lấy giá trị Q cho một trạng thái và hành động cụ thể."""
        return self.q_table.get(state, {}).get(action, 0.0)

    def update_q_value(self, state, action, reward, next_state, next_action):
        """Cập nhật giá trị Q dựa trên trạng thái, hành động, phần thưởng và trạng thái tiếp theo."""
        current_q = self.get_q_value(state, action)
        next_q = self.get_q_value(next_state, next_action)
        if state not in self.q_table:
            self.q_table[state] = {}
        self.q_table[state][action] = current_q + self.alpha * (
            reward + self.gamma * next_q - current_q
        )

    def choose_action(self, state):
        """Chọn hành động dựa trên chính sách ε-greedy."""
        if np.random.rand() < self.epsilon:
            return random.choice(self.actions)
        else:
            if state in self.q_table:
                q_values = self.q_table[state]
                max_action = max(
                    q_values, key=q_values.get
                )  # Hành động với giá trị Q lớn nhất
                return max_action
            else:
                return random.choice(
                    self.actions
                )  # Chọn ngẫu nhiên nếu chưa có Q-value


def get_sarsa_input_data(user_id):
    """Lấy dữ liệu cần thiết cho thuật toán SARSA từ cơ sở dữ liệu."""
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

        # Lấy dữ liệu từ bảng category và bill
        query = """
        SELECT c.id AS category_id, c.category_name, c.amount AS budget, c.actual_amount, c.percentage_limit,
               b.amount, b.date
        FROM "CATEGORY" c
        JOIN "BILL" b ON c.id = b.category_id
        WHERE b.user_id = %s;
        """
        cursor.execute(query, (user_id,))
        rows = cursor.fetchall()

        # Chuyển đổi kết quả thành định dạng JSON
        data = []
        for row in rows:
            data.append(
                {
                    "category_id": row[0],
                    "category_name": row[1],
                    "budget": row[2],
                    "actual_amount": row[3],
                    "percentage_limit": row[4],
                    "amount": row[5],
                    "date": row[6].strftime("%Y-%m-%d"),  # Định dạng lại ngày tháng
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


def discretize_spending_ratio(spending_ratio):
    """Chia nhóm tỷ lệ chi tiêu thành các trạng thái."""
    if spending_ratio < 0:
        return 0  # Đảm bảo không có tỷ lệ âm
    elif spending_ratio > 300:
        return 300  # Đảm bảo không vượt quá 300

    # Chia nhóm mỗi 10% và lấy giá trị trung bình
    return int((spending_ratio // 10) * 10 + 5)


def calculate_reward(spending_ratio):
    """Hàm tính toán phần thưởng dựa trên tỷ lệ chi tiêu."""
    if spending_ratio > 100:
        return -1  # Phần thưởng tiêu cực cho việc vượt ngân sách
    elif spending_ratio > 80:
        return 0  # Phần thưởng trung tính
    else:
        return 1  # Phần thưởng tích cực cho việc tiết kiệm


def generate_spending_recommendations(data):
    """Tạo ra các đề xuất chi tiêu và bảng Q dựa trên dữ liệu."""
    actions = [
        "Giảm giới hạn ngân sách",
        "không thay đổi ngân sách",
        "Tăng giới hạn ngân sách",
        "Giảm chi tiêu",
        "Tăng chi tiêu",
    ]
    sarsa = SARSA(actions)
    recommendations = []
    q_data = []  # Lưu thông tin bảng Q
    seen_recommendations = set()  # Sử dụng set để theo dõi các đề xuất đã thấy

    for item in data:
        actual_amount = int(item["actual_amount"])
        budget = int(item["budget"])
        category_name = item["category_name"]
        category_id = item["category_id"]

        # Tính toán tỷ lệ chi tiêu
        spending_ratio = (actual_amount / budget) * 100

        # Chia nhóm trạng thái
        state = discretize_spending_ratio(spending_ratio)  # Chia nhóm

        # Quy tắc gợi ý
        if spending_ratio < 60:
            action = random.choice(
                [actions[0], actions[4]]
            )  # "Giảm giới hạn ngân sách" hoặc "Tăng chi tiêu"
            recommendation = f"Bạn có thể {action.lower()} cho mục '{category_name}' vì tỷ lệ chi tiêu là {spending_ratio:.2f}%."
        elif 60 < spending_ratio < 90:
            action = actions[1]  # "không thay đổi ngân sách"
            recommendation = f"Không cần điều chỉnh ngân sách cho mục '{category_name}' vì tỷ lệ chi tiêu là {spending_ratio:.2f}%."
        elif 90 < spending_ratio < 150:
            action = random.choice(
                [actions[2], actions[3]]
            )  # "Tăng giới hạn ngân sách" hoặc "Giảm chi tiêu"
            recommendation = f"Bạn có thể {action.lower()} cho mục '{category_name}' vì tỷ lệ chi tiêu là {spending_ratio:.2f}%."
        else:  # spending_ratio > 150
            action = actions[3]  # "Giảm chi tiêu"
            recommendation = f"Có thể {action.lower()} cho mục '{category_name}' vì tỷ lệ chi tiêu là {spending_ratio:.2f}%."

        # Kiểm tra xem đề xuất đã tồn tại cho danh mục này chưa
        if (state, action) not in seen_recommendations:
            recommendations.append(
                {
                    "category_id": category_id,
                    "category_name": category_name,
                    "recommendation": recommendation,
                }
            )
            seen_recommendations.add(
                (state, action)
            )  # Thêm trạng thái và hành động vào set

        # Cập nhật Q-table và lưu thông tin Q
        reward = calculate_reward(spending_ratio)  # Tính toán phần thưởng
        next_state = discretize_spending_ratio(
            spending_ratio
        )  # Có thể thay đổi tùy theo yêu cầu
        next_action = sarsa.choose_action(next_state)  # Hành động tiếp theo
        sarsa.update_q_value(state, action, reward, next_state, next_action)

        # Thêm thông tin Q vào q_data
        q_data.append(
            {
                "state": state,
                "action": action,
                "q_value": sarsa.get_q_value(state, action),
            }
        )

    return recommendations, q_data


@sarsa_bp.route("/get-sarsa-input/<int:user_id>", methods=["GET"])
def get_sarsa_input(user_id):
    """Lấy dữ liệu cần thiết cho thuật toán SARSA và tạo gợi ý chi tiêu."""
    result = get_sarsa_input_data(user_id)

    if "data" in result:
        # Tạo gợi ý từ dữ liệu
        recommendations, q_data = generate_spending_recommendations(result["data"])

        # Sắp xếp q_data theo state
        q_data_sorted = sorted(q_data, key=lambda x: x["state"])

        return (
            jsonify(
                {
                    "status": "success",
                    "recommendations": recommendations,  # Gợi ý chi tiêu
                    "q_table": q_data_sorted,  # Bảng Q riêng biệt và đã sắp xếp
                }
            ),
            200,
        )
    else:
        return jsonify({"status": result["status"], "message": result["message"]}), 500
