"""
小车端蓝牙 SPP 服务 — 与安卓 App 通信

物理依赖:
  蓝牙适配器: 树莓派 4B 板载蓝牙 (无需额外硬件)
  蓝牙名称: RoboClean-XXXX (可在代码中修改)
  通信距离: ~10m

协议:
  帧格式: [0xAA] [长度] [指令] [数据...] [异或校验]
  App→车: 0x01=查询 0x02=设时间 0x03=设路线 0x04=急停 0x05=启停
  车→App: 0x11=状态数据  0x12=确认/错误

发布: /bt/command (收到的指令)
订阅: /bt/response (发送给 App 的数据)
"""

import struct
import threading
import json
import rclpy
from rclpy.node import Node
from std_msgs.msg import String, Float32, Bool

try:
    import bluetooth
    HAS_BLUETOOTH = True
except ImportError:
    HAS_BLUETOOTH = False


# ── 协议常量 ──
FRAME_HEADER: int = 0xAA

CMD_QUERY_STATUS: int = 0x01   # App→车: 查询状态
CMD_SET_SCHEDULE: int = 0x02   # App→车: 设置工作时间
CMD_SET_ROUTE: int    = 0x03   # App→车: 设置路线
CMD_EMERGENCY: int    = 0x04   # App→车: 紧急停止
CMD_START_STOP: int   = 0x05   # App→车: 启动/停止工作

RSP_STATUS: int       = 0x11   # 车→App: 状态数据
RSP_ACK: int          = 0x12   # 车→App: 确认


class BluetoothServer(Node):
    """蓝牙 SPP 服务节点"""

    def __init__(self):
        super().__init__('bluetooth_server')

        self.declare_parameter('bt_name', 'RoboClean-001')
        self.declare_parameter('bt_channel', 1)
        self.declare_parameter('battery_full_voltage', 54.6)
        self.declare_parameter('battery_empty_voltage', 42.0)
        self.declare_parameter('battery_capacity_ah', 60.0)

        self.bt_name = self.get_parameter('bt_name').value
        self.bt_channel = self.get_parameter('bt_channel').value
        self.bat_full_v = self.get_parameter('battery_full_voltage').value
        self.bat_empty_v = self.get_parameter('battery_empty_voltage').value

        # ── 共享状态 (线程安全) ──
        self._lock = threading.Lock()
        self._battery_v: float = self.bat_full_v
        self._total_km: float = 0.0
        self._working: bool = False
        self._temperature: int = 25

        # ── 连接状态 ──
        self.connected: bool = False

        # 订阅状态更新
        self.create_subscription(Float32, '/battery/voltage', self._on_battery_v, 10)
        self.create_subscription(Float32, '/total_distance', self._on_mileage, 10)
        self.create_subscription(String, '/motor/status', self._on_motor_status, 10)

        # 发布收到的指令
        self.cmd_pub = self.create_publisher(String, '/bt/command', 10)
        self.status_pub = self.create_publisher(String, '/bt/status', 10)

        # 蓝牙线程
        self.server_sock = None
        self.client_sock = None
        self.running: bool = True
        if HAS_BLUETOOTH:
            self.bt_thread = threading.Thread(target=self._bt_loop, daemon=True)
            self.bt_thread.start()
            self.get_logger().info(f'蓝牙服务启动: {self.bt_name}')
        else:
            self.get_logger().warn('PyBluez 未安装，蓝牙服务运行在模拟模式')

        # 定时器: 定时发送状态
        self.timer = self.create_timer(1.0, self._send_status)

    # ── 状态读取 (线程安全) ──

    def _get_battery_pct(self) -> float:
        """48V 系统: 电压 → 百分比 (参数化阈值)"""
        with self._lock:
            v = self._battery_v
        span = self.bat_full_v - self.bat_empty_v
        if span <= 0:
            return 100.0
        return max(0.0, min(100.0, (v - self.bat_empty_v) / span * 100.0))

    def _get_working(self) -> bool:
        with self._lock:
            return self._working

    def _get_total_km(self) -> float:
        with self._lock:
            return self._total_km

    def _get_temperature(self) -> int:
        with self._lock:
            return self._temperature

    # ── 状态更新回调 (ROS 主线程) ──

    def _on_battery_v(self, msg: Float32) -> None:
        with self._lock:
            self._battery_v = msg.data

    def _on_mileage(self, msg: Float32) -> None:
        with self._lock:
            self._total_km = msg.data / 1000.0   # m → km

    def _on_motor_status(self, msg: String) -> None:
        # 通过 motor_controller 的 status 消息判断是否在工作中
        # 格式: "cmd=(L,R)rpm act=(L,R)rpm V=... age=..."
        is_working = 'act=' in msg.data
        with self._lock:
            self._working = is_working

    # ── 主循环 ──

    def _bt_loop(self) -> None:
        """蓝牙 SPP 主循环 (运行在独立线程)"""
        try:
            self.server_sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
            self.server_sock.bind(("", bluetooth.PORT_ANY))
            self.server_sock.listen(1)

            bluetooth.advertise_service(
                self.server_sock, "RoboClean",
                service_id="00001101-0000-1000-8000-00805F9B34FB",
                service_classes=["00001101-0000-1000-8000-00805F9B34FB"],
                profiles=[bluetooth.SERIAL_PORT_PROFILE])

            self.get_logger().info('等待蓝牙连接...')

            while self.running:
                self.client_sock, client_info = self.server_sock.accept()
                self.connected = True
                self.get_logger().info(f'已连接: {client_info}')
                self.status_pub.publish(String(data='connected'))

                try:
                    while self.running and self.connected:
                        data = self.client_sock.recv(1024)
                        if not data:
                            break
                        self._parse_frame(data)
                except bluetooth.BluetoothError:
                    pass
                finally:
                    self.connected = False
                    if self.client_sock:
                        self.client_sock.close()
                    self.client_sock = None
                    self.get_logger().info('连接断开')
                    self.status_pub.publish(String(data='disconnected'))
        except Exception as e:
            self.get_logger().error(f'蓝牙异常: {e}')

    # ── 协议解析 ──

    def _parse_frame(self, data: bytes) -> None:
        """解析 App 发来的指令帧"""
        if len(data) < 4 or data[0] != FRAME_HEADER:
            return
        length = data[1]
        cmd = data[2]
        payload = data[3:3 + length - 3] if length > 3 else b''
        checksum_byte = data[3 + length - 3] if len(data) > 3 + length - 3 else 0

        # 异或校验
        calc = FRAME_HEADER ^ length ^ cmd
        for b in payload:
            calc ^= b
        if calc != checksum_byte:
            return

        self.get_logger().debug(f'收到指令: 0x{cmd:02X}')

        if cmd == CMD_QUERY_STATUS:
            self._send_status()
        elif cmd == CMD_SET_SCHEDULE:
            schedule = json.loads(payload.decode())
            self.cmd_pub.publish(String(data=json.dumps({'cmd': 'schedule', 'data': schedule})))
            self._send_ack(True)
        elif cmd == CMD_SET_ROUTE:
            route = json.loads(payload.decode())
            self.cmd_pub.publish(String(data=json.dumps({'cmd': 'route', 'data': route})))
            self._send_ack(True)
        elif cmd == CMD_EMERGENCY:
            self.cmd_pub.publish(String(data=json.dumps({'cmd': 'emergency_stop'})))
            self._send_ack(True)
        elif cmd == CMD_START_STOP:
            start = payload[0] if payload else 0
            self.cmd_pub.publish(String(data=json.dumps({'cmd': 'start_stop', 'start': bool(start)})))
            self._send_ack(True)

    # ── 发送 (线程安全读取) ──

    def _send_status(self) -> None:
        """发送状态数据帧: 电池% + 电压 + 里程 + 工作状态 + 温度"""
        payload = struct.pack(
            '<Bf f B B',
            int(self._get_battery_pct()),
            self._battery_v,       # 电压从 lock 外直接读 (float atomic on CPython)
            self._get_total_km(),
            1 if self._get_working() else 0,
            self._get_temperature()
        )
        self._send_frame(RSP_STATUS, payload)

    def _send_ack(self, success: bool) -> None:
        self._send_frame(RSP_ACK, bytes([1 if success else 0]))

    def _send_frame(self, cmd: int, payload: bytes) -> None:
        """构建协议帧并发送"""
        if self.client_sock is None:
            return
        length = 3 + len(payload)
        checksum = FRAME_HEADER ^ length ^ cmd
        for b in payload:
            checksum ^= b
        frame = bytes([FRAME_HEADER, length, cmd]) + payload + bytes([checksum])
        try:
            self.client_sock.send(frame)
        except Exception:
            self.connected = False

    def destroy_node(self) -> None:
        self.running = False
        if self.client_sock:
            self.client_sock.close()
        if self.server_sock:
            self.server_sock.close()
        super().destroy_node()


def main(args=None):
    rclpy.init(args=args)
    rclpy.spin(BluetoothServer())
    rclpy.shutdown()

if __name__ == '__main__':
    main()
