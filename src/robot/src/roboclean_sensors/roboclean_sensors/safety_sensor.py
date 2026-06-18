"""
安全传感器节点

物理依赖 (装车后必须核实):
  GPIO 引脚分配         ← 必须按实际接线修改 PIN_* 常量!
  安全触边安装位置 (前左/前右) ← 前后方向定义
  急停按钮安装位置       ← 操作方便、醒目的位置
  超声波 ×4 安装位置    ← 前后左右，朝向无误
  超声波-围栏侧         ← 用于 /ultrasonic/fence，必须对准围栏

监测: 安全触边 + 急停按钮 + 超声波 ×4
触发时 → /safety/stop → 电机急停
发布: /safety/stop  /safety/warning  /ultrasonic/fence
"""

import threading
import time

import rclpy
from rclpy.node import Node
from std_msgs.msg import Bool, Float32, String

# GPIO 引脚（树莓派 4B BCM 编号）
PIN_BUMPER_LEFT: int = 17  # 安全触边左
PIN_BUMPER_RIGHT: int = 27  # 安全触边右
PIN_EMG_BUTTON: int = 22  # 急停按钮

PIN_ULTRASONIC_FRONT: tuple[int, int] = (23, 24)
PIN_ULTRASONIC_REAR: tuple[int, int] = (25, 8)
PIN_ULTRASONIC_LEFT: tuple[int, int] = (6, 5)
PIN_ULTRASONIC_RIGHT: tuple[int, int] = (16, 12)

# 安全距离 (米)
MIN_DISTANCE: float = 0.3
# 超声波最大测距超时 (秒)
ULTRA_TIMEOUT_S: float = 0.04  # 40ms ≈ 6.8m


class SafetySensorNode(Node):
    """安全传感器监测节点"""

    def __init__(self):
        super().__init__('safety_sensor')

        self.declare_parameter('use_hardware', False)
        self.use_hw: bool = self.get_parameter('use_hardware').value

        self.GPIO = None
        if self.use_hw:
            self._init_gpio()
        else:
            self.get_logger().info('安全传感器运行在模拟模式')

        # ── 超声波状态机 (非阻塞) ──
        self._ultra_lock = threading.Lock()
        self._ultra_trig_time: float = 0.0
        self._ultra_measuring: bool = False
        self._ultra_pulse_start: float = 0.0
        self._ultra_pulse_end: float = 0.0
        self._ultra_distance: float | None = None

        # 发布
        self.safety_pub = self.create_publisher(Bool, '/safety/stop', 10)
        self.warning_pub = self.create_publisher(String, '/safety/warning', 10)
        self.ultra_fence_pub = self.create_publisher(Float32, '/ultrasonic/fence', 10)

        # 定时器 20Hz
        self.timer = self.create_timer(0.05, self.check_safety)

        self.get_logger().info('安全传感器节点已启动')

    def _init_gpio(self) -> None:
        try:
            import RPi.GPIO as GPIO

            GPIO.setmode(GPIO.BCM)
            GPIO.setup(PIN_BUMPER_LEFT, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.setup(PIN_BUMPER_RIGHT, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            GPIO.setup(PIN_EMG_BUTTON, GPIO.IN, pull_up_down=GPIO.PUD_UP)
            self.GPIO = GPIO
            self.get_logger().info('GPIO 已初始化')
        except ImportError:
            self.get_logger().warn('RPi.GPIO 不可用，使用模拟模式')
            self.use_hw = False

    def check_safety(self) -> None:
        """检查安全状态 (20Hz, 非阻塞)"""
        trigger: bool = False
        reason: str = ''

        if self.use_hw and self.GPIO is not None:
            GPIO = self.GPIO
            if GPIO.input(PIN_BUMPER_LEFT) == GPIO.LOW:
                trigger = True
                reason = '安全触边左触发'
            if GPIO.input(PIN_BUMPER_RIGHT) == GPIO.LOW:
                trigger = True
                if not reason:
                    reason = '安全触边右触发'
                else:
                    reason = '安全触边双边触发'
            if GPIO.input(PIN_EMG_BUTTON) == GPIO.LOW:
                trigger = True
                reason = reason or '急停按钮按下'

            # 读取侧方超声波 (非阻塞状态机)
            self._read_ultrasonic_nonblocking()

        if trigger:
            self.safety_pub.publish(Bool(data=True))
            self.warning_pub.publish(String(data=reason))
            self.get_logger().warn(f'安全触发: {reason}')

    def _read_ultrasonic_nonblocking(self) -> None:
        """
        非阻塞超声波读取 (状态机, 在 20Hz 定时器中调用)

        状态转换: IDLE → TRIGGERED → WAITING_RISE → WAITING_FALL → DONE
        每次调用执行一步，确保不阻塞定时器。
        """
        if self.GPIO is None:
            return
        GPIO = self.GPIO
        trig, echo = PIN_ULTRASONIC_LEFT

        with self._ultra_lock:
            if not self._ultra_measuring:
                # 发送 10us 触发脉冲
                GPIO.output(trig, GPIO.HIGH)
                self._ultra_trig_time = time.time()
                self._ultra_measuring = True
                return

            elapsed = time.time() - self._ultra_trig_time

            if elapsed < 0.00002:  # 还没到 20us — 保持 HIGH
                return

            # 拉低 trig
            if elapsed < 0.0001:
                GPIO.output(trig, GPIO.LOW)
                return

            # 等待 echo 上升沿
            if self._ultra_pulse_start == 0.0:
                if GPIO.input(echo) == GPIO.HIGH:
                    self._ultra_pulse_start = time.time()
                elif elapsed > ULTRA_TIMEOUT_S:
                    self._ultra_measuring = False  # 超时
                return

            # 等待 echo 下降沿
            if self._ultra_pulse_end == 0.0:
                if GPIO.input(echo) == GPIO.LOW:
                    self._ultra_pulse_end = time.time()
                elif (time.time() - self._ultra_pulse_start) > ULTRA_TIMEOUT_S:
                    self._ultra_pulse_end = self._ultra_pulse_start  # 超时, 用 start 作为 end
                else:
                    return

            # 计算距离
            duration = self._ultra_pulse_end - self._ultra_pulse_start
            distance = duration * 17150.0  # cm → 声速 343m/s / 2
            if 2.0 < distance < 600.0:  # 有效范围 2cm-6m
                self._ultra_distance = distance
                self.ultra_fence_pub.publish(Float32(data=distance / 100.0))  # cm → m

            # 重置状态
            self._ultra_measuring = False
            self._ultra_pulse_start = 0.0
            self._ultra_pulse_end = 0.0

    def destroy_node(self) -> None:
        if self.use_hw and self.GPIO is not None:
            self.GPIO.cleanup()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    rclpy.spin(SafetySensorNode())
    rclpy.shutdown()


if __name__ == '__main__':
    main()
