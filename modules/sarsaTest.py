from flask import Blueprint, jsonify
import numpy as np
import random

sarsa_test_bp = Blueprint("sarsa-test", __name__)

class QLearning:
    # Khởi tạo
    def __init__(self, action, alpha=0.1, gamma=0.9, epsilon=0.1):
        self.q_table = {}  # Khởi tạo Q-table là 1 từ điển
        self.action = action
        self.alpha = alpha
        self.gamma = gamma
        self.epsilon = epsilon

    # Hàm lấy Q_value
    def get_q_value(self, state, action):
        return self.q_table.get(state, {}).get(action, 0.0)

    # Hàm cập nhật Q_table
    def update_q_table(self, state, action, reward, next_state, next_action):
        current_q = self.get_q_value(state, action)  # Lấy giá trị Q hiện tại
        next_q = self.get_q_value(next_state, next_action)  # Lấy giá trị Q kế tiếp
        if state not in self.q_table:
            self.q_table[state] = {}  # Khởi tạo Q_table nếu chưa có

        # Cập nhật giá trị Q theo công thức
        self.q_table[state][action] = current_q + self.alpha * (
            reward + self.gamma * next_q - current_q
        )

    # Hàm chọn hành động
    def choose_action(self, state):
        # Khám phá
        if np.random.rand() < self.epsilon:
            return random.choice(self.action)

        # Khai thác
        else:
            if state in self.q_table:
                q_values = self.q_table[state]  # Lấy giá trị Q cho state hiện tại
                max_action = max(
                    q_values, key=q_values.get
                )  # Tìm action có giá trị q cao nhất
                return max_action
            else:
                return random.choice(self.action)

    def get_q_table(self):
        return self.q_table

@sarsa_test_bp.route("/get-sarsa-test", methods=["GET"])
def get_q_table():
    # Danh sách hành động
    actions = [
        "Giảm giới hạn ngân sách",
        "không thay đổi ngân sách",
        "Tăng giới hạn ngân sách",
        "Giảm chi tiêu",
        "Tăng chi tiêu",
    ]

    # Danh sách các state
    states = ["low", "medium", "high", "exceeded"]

    # Lấy phần thưởng từ môi trường dựa trên state
    rewards = {
        "low": 2,
        "medium": 1,
        "high": 0,
        "exceeded": -1
    }

    next_actions = {
        "low": "Giảm giới hạn ngân sách",
        "medium": "Không thay đổi ngân sách",
        "high": random.choice(["Tăng giới hạn ngân sách", "Giảm chi tiêu"]),  # Chọn ngẫu nhiên
        "exceeded": "Giảm chi tiêu"
    }

    # Khởi tạo giá trị Q_learning
    q_learning = QLearning(actions)

    num_trial = 500

    for trial in range(num_trial):
        state = random.choice(states) # Khởi tạo state ngẫu nhiên
        action = q_learning.choose_action(state) # chọn hành động theo Q_learning

        reward = rewards[state]
        next_action = next_actions[state]

        # Xác định trạng thái tiếp theo dựa trên hành động đã chọn
        if next_action == "Giảm giới hạn ngân sách":
            next_state = "low" if state == "medium" else state
        elif next_action == "Không thay đổi ngân sách":
            next_state = state  # Giữ nguyên trạng thái
        elif next_action == "Tăng giới hạn ngân sách":
            next_state = "high" if state == "low" else state
        elif next_action == "Giảm chi tiêu":
            next_state = "exceeded" if state == "high" else state

        next_action = q_learning.choose_action(next_state)

        q_learning.update_q_table(state, action, reward, next_state, next_action)

    # Lấy Q_table hiện tại
    q_table = q_learning.get_q_table()

    # Trả về q_table dưới dạng JSON
    return jsonify({"status": "success", "q_table": q_table})
    


