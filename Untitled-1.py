# api/dashboard.py
from flask import Blueprint, jsonify
import random
import time

# 创建一个蓝图，方便模块化组织路由
dashboard_bp = Blueprint('dashboard', __name__)

# --- 模拟数据源 (在实际项目中，这些数据应来自数据库或核心引擎) ---
_evolution_data = []
_candidate_list = [
    {"id": "C001", "name": "候选人 A", "status": "处理中"},
    {"id": "C002", "name": "候选人 B", "status": "等待中"},
    {"id": "C003", "name": "候选人 C", "status": "已完成"},
]

# 初始化一些历史数据用于趋势图
for i in range(1, 21):
    _evolution_data.append({
        "generation": i,
        "success_rate": round(random.uniform(50, 95), 2)
    })


@dashboard_bp.route('/api/dashboard/overview', methods=['GET'])
def get_overview():
    """
    获取看板的概览数据。
    对应任务描述中的：
    - 展示当前的“进化代数”
    - 匹配成功率趋势
    """
    # 获取最新的一条记录作为当前状态
    current_status = _evolution_data[-1] if _evolution_data else {}

    # 返回的数据结构
    response_data = {
        "current_generation": current_status.get("generation", 0),
        "current_success_rate": current_status.get("success_rate", 0),
        "trend_data": _evolution_data  # 返回所有历史数据用于绘制趋势图
    }

    return jsonify(response_data)


@dashboard_bp.route('/api/dashboard/candidates', methods=['GET'])
def get_candidates():
    """
    获取正在处理的候选人列表。
    对应任务描述中的：
    - 实时显示正在处理的候选人列表
    """
    # 这里可以添加逻辑来过滤出状态为“处理中”的候选人
    processing_candidates = [c for c in _candidate_list if c['status'] == '处理中']

    return jsonify(processing_candidates)


# --- 辅助函数：模拟数据更新 (可选，用于演示动态效果) ---
def simulate_data_update():
    """
    模拟核心引擎在后台运行，不断更新数据。
    你可以在主程序启动时在一个新线程中调用此函数。
    """
    while True:
        time.sleep(5)  # 每5秒更新一次
        last_gen = _evolution_data[-1]['generation']
        new_gen = last_gen + 1
        new_rate = round(random.uniform(max(50, _evolution_data[-1]['success_rate'] - 10), min(99, _evolution_data[-1]['success_rate'] + 10)), 2)

        _evolution_data.append({"generation": new_gen, "success_rate": new_rate})
        print(f"Data updated: Generation {new_gen}, Success Rate {new_rate}%")