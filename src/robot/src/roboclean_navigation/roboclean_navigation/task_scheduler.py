"""
离线任务调度器 — 蓝牙断开后仍自主运行

职责:
  1. 接收 App 发来的工作时间表 (JSON)
  2. 持久化到本地文件 (~/roboclean_schedule.json)
  3. 每秒检查当前时间是否在任务时间段内
  4. 到时间 → 启动推料任务 (fence_follower)
  5. 时间结束 → 停止 + 触发回充检查

发布: /task/start (Bool)  /task/stop (Bool)
订阅: /bt/command (String, JSON)
"""

import json
import os
from datetime import datetime
from typing import Any

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, String

# 中文星期 → Python weekday (0=Mon, 6=Sun)
DAY_MAP: dict[str, int] = {
    '周一': 0,
    '周二': 1,
    '周三': 2,
    '周四': 3,
    '周五': 4,
    '周六': 5,
    '周日': 6,
}


class TaskScheduler(Node):
    """离线任务调度器"""

    def __init__(self):
        super().__init__('task_scheduler')

        # 持久化文件路径
        self.declare_parameter('schedule_file', os.path.expanduser('~/roboclean_schedule.json'))
        self._schedule_file = self.get_parameter('schedule_file').value

        # 任务数据
        self._slots: list[dict[str, Any]] = []
        self._task_active: bool = False
        self._last_check_minute: int = -1

        # 加载已保存的时间表
        self._load_schedule()

        # 订阅 App 发来的指令 (通过 bt_server 转发)
        self.create_subscription(String, '/bt/command', self._on_command, 10)

        # 发布任务控制
        self._start_pub = self.create_publisher(Bool, '/task/start', 10)
        self._stop_pub = self.create_publisher(Bool, '/task/stop', 10)
        self._status_pub = self.create_publisher(String, '/task/status', 10)

        # 定时器: 每秒检查
        self._timer = self.create_timer(1.0, self._check_schedule)

        self.get_logger().info(f'任务调度器已启动 | 已加载 {len(self._slots)} 个时间段')

    # ── 指令处理 ──

    def _on_command(self, msg: String) -> None:
        """接收 /bt/command → 解析 schedule 指令"""
        try:
            data = json.loads(msg.data)
        except json.JSONDecodeError:
            return

        cmd = data.get('cmd', '')
        if cmd == 'schedule':
            slots = data.get('data', {}).get('slots', [])
            self._save_schedule(slots)
            self.get_logger().info(f'收到工作时间表: {len(slots)} 个时间段')

    # ── 持久化 ──

    def _save_schedule(self, slots: list[dict[str, Any]]) -> None:
        """保存到本地文件"""
        self._slots = slots
        try:
            with open(self._schedule_file, 'w', encoding='utf-8') as f:
                json.dump(
                    {'slots': slots, 'updated': datetime.now().isoformat()},
                    f,
                    ensure_ascii=False,
                    indent=2,
                )
            self.get_logger().info(f'时间表已保存: {self._schedule_file}')
        except OSError as e:
            self.get_logger().error(f'保存失败: {e}')

    def _load_schedule(self) -> None:
        """从本地文件加载"""
        try:
            with open(self._schedule_file, encoding='utf-8') as f:
                data = json.load(f)
                self._slots = data.get('slots', [])
                updated = data.get('updated', '未知')
                self.get_logger().info(f'加载已有时间表 ({updated}): {len(self._slots)} 个时间段')
        except FileNotFoundError:
            self.get_logger().info('无已有时间表文件，等待 App 设置')
        except (json.JSONDecodeError, OSError) as e:
            self.get_logger().warn(f'加载失败: {e}')

    # ── 定时检查 ──

    def _check_schedule(self) -> None:
        """每秒检查一次: 是否在任务时间段内"""
        now = datetime.now()
        current_minute = now.hour * 60 + now.minute
        weekday = now.weekday()  # 0=Mon, 6=Sun

        # 每分钟只检查一次 (避免1秒内重复触发)
        if current_minute == self._last_check_minute:
            return
        self._last_check_minute = current_minute

        in_slot = self._is_in_time_slot(weekday, now.hour, now.minute)

        if in_slot and not self._task_active:
            self._start_task()
        elif not in_slot and self._task_active:
            self._stop_task()

    def _is_in_time_slot(self, weekday: int, hour: int, minute: int) -> bool:
        """判断当前时间是否在任一时间段内"""
        current_min = hour * 60 + minute
        for slot in self._slots:
            if not slot.get('enabled', True):
                continue
            day_name = slot.get('dayOfWeek', '')
            slot_weekday = DAY_MAP.get(day_name)
            if slot_weekday is None or slot_weekday != weekday:
                continue
            start = slot['startHour'] * 60 + slot['startMinute']
            end = slot['endHour'] * 60 + slot['endMinute']
            if start <= current_min < end:
                return True
        return False

    # ── 任务控制 ──

    def _start_task(self) -> None:
        self._task_active = True
        self._start_pub.publish(Bool(data=True))
        self._status_pub.publish(String(data='task_started'))
        self.get_logger().info('⏰ 进入工作时间 → 启动推料')

    def _stop_task(self) -> None:
        self._task_active = False
        self._stop_pub.publish(Bool(data=True))
        self._status_pub.publish(String(data='task_stopped'))
        self.get_logger().info('⏰ 工作时间结束 → 停止推料')

    def destroy_node(self) -> None:
        if self._task_active:
            self._stop_pub.publish(Bool(data=True))
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    rclpy.spin(TaskScheduler())
    rclpy.shutdown()


if __name__ == '__main__':
    main()
