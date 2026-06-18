"""
CANopen 驱动模块 — ZBLD.C20-800LRC

寄存器地址参考 docs/driver-c20-800lrc.md
通信方式: SocketCAN + canopen 库

⚠️ 重要: 多个节点共享同一个 canopen.Network 实例。
  使用 get_shared_network() 获取全局单例，避免总线冲突。
"""

from __future__ import annotations

import threading

import canopen

# ── 共享 Network 单例 ──
_shared_network: canopen.Network | None = None
_network_lock = threading.Lock()


def get_shared_network(channel: str = 'can0', bustype: str = 'socketcan') -> canopen.Network:
    """获取全局 CANopen Network 单例 — 多节点共享, 避免总线冲突"""
    global _shared_network
    if _shared_network is None:
        with _network_lock:
            if _shared_network is None:
                _shared_network = canopen.Network()
                _shared_network.connect(channel=channel, bustype=bustype)
    return _shared_network


def disconnect_shared_network() -> None:
    """断开共享 Network (进程退出时调用)"""
    global _shared_network
    if _shared_network is not None:
        _shared_network.disconnect()
        _shared_network = None


# ── 寄存器地址 (从说明书) ──
REG_CONTROL = 0x2000  # 控制命令
REG_SPEED_SET = 0x2001  # 设定速度 (RPM)
REG_POLE_PAIRS = 0x2002  # 极对数
REG_ACC_TIME = 0x2003  # 加速时间 (0.1S)
REG_DEC_TIME = 0x2004  # 减速时间 (0.1S)
REG_CTRL_MODE = 0x2005  # 控制模式
REG_CMD_SRC = 0x2006  # 运行指令选择
REG_SPEED_SRC = 0x2007  # 速度给定选择
REG_NODE_ID = 0x2008  # 通讯地址
REG_BAUDRATE = 0x2009  # 波特率
REG_STOP_MODE = 0x2012  # 停机方式

REG_STATUS1 = 0x2100  # 状态字1
REG_STATUS2 = 0x2101  # 状态字2
REG_FAULT_CODE = 0x2102  # 故障码
REG_DRIVE_ID = 0x2103  # 驱动器识别

REG_ACT_SPEED = 0x2202  # 实际转速 (RPM)
REG_ACT_CURRENT = 0x2203  # 实际电流 (0.1A)
REG_BUS_VOLT = 0x2204  # 母线电压 (0.1V)
REG_TEMP = 0x2205  # 模块温度 (C)

# ── 控制命令 ──
CMD_FWD_RUN = 0x0001  # 正转
CMD_REV_RUN = 0x0002  # 反转
CMD_FWD_JOG = 0x0003  # 正转点动
CMD_REV_JOG = 0x0004  # 反转点动
CMD_STOP = 0x0005  # 减速停机
CMD_EMG_STOP = 0x0006  # 紧急停止
CMD_FAULT_RST = 0x0007  # 故障复位


class C20Driver:
    """ZBLD.C20-800LRC CANopen 驱动封装"""

    def __init__(
        self,
        node_id: int,
        channel: str = 'can0',
        eds_file: str | None = None,
        network: canopen.Network | None = None,
    ):
        self.node_id = node_id

        # 使用共享 Network (避免多节点各自创建导致总线冲突)
        if network is not None:
            self.network = network
        else:
            self.network = get_shared_network(channel)
        self._owns_network = False  # 共享模式, destroy 时不关 bus

        # 添加从节点
        if eds_file:
            self.node = self.network.add_node(node_id, eds_file)
        else:
            self.node = self.network.add_node(node_id, object_dictionary={})

    def enter_operational(self):
        """进入 Operational 状态"""
        self.node.nmt.state = 'OPERATIONAL'

    def enter_pre_operational(self):
        """进入 Pre-Operational 状态"""
        self.node.nmt.state = 'PRE-OPERATIONAL'

    def configure_for_comm_control(self):
        """配置为通讯控制模式"""
        self.node.sdo[REG_CMD_SRC].raw = 2  # 运行指令=通讯
        self.node.sdo[REG_SPEED_SRC].raw = 3  # 速度给定=Modbus通讯

    # ── 运动控制 ──

    def set_speed(self, rpm: int):
        """设置目标速度 (RPM)"""
        rpm = max(-3000, min(3000, rpm))
        self.node.sdo[REG_SPEED_SET].raw = abs(rpm)
        if rpm >= 0:
            self.node.sdo[REG_CONTROL].raw = CMD_FWD_RUN
        else:
            self.node.sdo[REG_CONTROL].raw = CMD_REV_RUN

    def stop(self, emergency: bool = False):
        """停机"""
        cmd = CMD_EMG_STOP if emergency else CMD_STOP
        self.node.sdo[REG_CONTROL].raw = cmd

    def fault_reset(self):
        """故障复位"""
        self.node.sdo[REG_CONTROL].raw = CMD_FAULT_RST

    # ── 状态读取 ──

    def get_status(self) -> dict:
        """读取驱动器状态"""
        s1 = self.node.sdo[REG_STATUS1].raw
        return {
            'running': s1 in (0x0001, 0x0002),
            'forward': s1 == 0x0001,
            'reverse': s1 == 0x0002,
            'stopped': s1 == 0x0003,
            'fault': s1 == 0x0004,
            'off': s1 == 0x0005,
            'brake': s1 == 0x0006,
            'raw': s1,
        }

    def get_actual_speed(self) -> int:
        """读取实际转速 (RPM)"""
        return self.node.sdo[REG_ACT_SPEED].raw

    def get_actual_current(self) -> float:
        """读取实际电流 (A)"""
        return self.node.sdo[REG_ACT_CURRENT].raw * 0.1

    def get_bus_voltage(self) -> float:
        """读取母线电压 (V)"""
        return self.node.sdo[REG_BUS_VOLT].raw * 0.1

    def get_temperature(self) -> int:
        """读取模块温度 (C)"""
        return self.node.sdo[REG_TEMP].raw

    def get_fault_code(self) -> int:
        """读取故障码"""
        return self.node.sdo[REG_FAULT_CODE].raw

    def is_healthy(self) -> bool:
        """检查是否正常"""
        return self.get_fault_code() == 0

    # ── 配置 ──

    def set_acceleration(self, time_100ms: int):
        """设置加速时间 (单位: 0.1 秒)"""
        self.node.sdo[REG_ACC_TIME].raw = time_100ms

    def set_deceleration(self, time_100ms: int):
        """设置减速时间 (单位: 0.1 秒)"""
        self.node.sdo[REG_DEC_TIME].raw = time_100ms

    def disconnect(self) -> None:
        """断开本节点 (不关闭共享 bus)"""
        if self._owns_network:
            self.network.disconnect()
        # 共享模式下不做任何事 — 由 disconnect_shared_network() 统一清理


class DriveSystem:
    """三驱动器系统 (左轮 + 右轮 + 清洁刷) — 共享 CANopen Network"""

    def __init__(
        self, left_id: int = 1, right_id: int = 2, brush_id: int = 3, channel: str = 'can0'
    ):
        # 三个驱动器共享同一个 Network
        network = get_shared_network(channel)
        self.left = C20Driver(left_id, channel, network=network)
        self.right = C20Driver(right_id, channel, network=network)
        self.brush = C20Driver(brush_id, channel, network=network)

    def enter_operational_all(self):
        """全部进入运行状态"""
        for d in [self.left, self.right, self.brush]:
            d.enter_operational()
            d.configure_for_comm_control()

    def set_wheel_speeds(self, left_rpm: int, right_rpm: int):
        """设置左右轮速度 (RPM)"""
        self.left.set_speed(left_rpm)
        self.right.set_speed(right_rpm)

    def set_brush(self, rpm: int = 500):
        """控制清洁刷"""
        self.brush.set_speed(rpm)

    def stop_brush(self):
        """停止清洁刷"""
        self.brush.stop()

    def emergency_stop(self):
        """全线急停"""
        for d in [self.left, self.right, self.brush]:
            d.stop(emergency=True)

    def stop_all(self):
        """全线减速停止"""
        for d in [self.left, self.right, self.brush]:
            d.stop()

    def get_all_status(self) -> dict:
        """读取全部状态"""
        return {
            'left': self.left.get_status(),
            'right': self.right.get_status(),
            'brush': self.brush.get_status(),
            'bus_voltage': self.left.get_bus_voltage(),
            'left_current': self.left.get_actual_current(),
            'right_current': self.right.get_actual_current(),
            'brush_current': self.brush.get_actual_current(),
            'left_temp': self.left.get_temperature(),
            'right_temp': self.right.get_temperature(),
        }

    def shutdown(self) -> None:
        """关闭所有连接"""
        disconnect_shared_network()
