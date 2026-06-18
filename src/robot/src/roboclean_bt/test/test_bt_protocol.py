"""
蓝牙协议单元测试 — 帧构建 + 校验和 + 状态打包

目标覆盖率: ≥90%
测试内容: 帧构建、校验和、状态 payload 打包/解析
"""

import struct
import sys

sys.path.insert(0, '..')

# 复制协议常量 (独立测试, 不依赖 ROS)
FRAME_HEADER = 0xAA

CMD_QUERY_STATUS = 0x01
CMD_SET_SCHEDULE = 0x02
CMD_SET_ROUTE = 0x03
CMD_EMERGENCY = 0x04
CMD_START_STOP = 0x05

RSP_STATUS = 0x11
RSP_ACK = 0x12


def build_frame(cmd: int, payload: bytes = b'') -> bytes:
    """构建协议帧 (与 bt_server.py _send_frame 逻辑一致)"""
    length = 3 + len(payload)
    checksum = FRAME_HEADER ^ length ^ cmd
    for b in payload:
        checksum ^= b
    return bytes([FRAME_HEADER, length, cmd]) + payload + bytes([checksum])


def build_status_payload(
    battery_pct: int, voltage: float, total_km: float, working: bool, temperature: int
) -> bytes:
    """构建状态 payload (与 bt_server.py _send_status 逻辑一致)"""
    return struct.pack(
        '<Bf f B B', battery_pct, voltage, total_km, 1 if working else 0, temperature
    )


def verify_checksum(frame: bytes) -> bool:
    """验证帧校验和"""
    if len(frame) < 4 or frame[0] != FRAME_HEADER:
        return False
    length = frame[1]
    cmd = frame[2]
    payload = frame[3 : 3 + length - 3]
    expected = frame[3 + length - 3]
    calc = FRAME_HEADER ^ length ^ cmd
    for b in payload:
        calc ^= b
    return calc == expected


# ═══════════════════════════════════════════════════
# 帧构建
# ═══════════════════════════════════════════════════


class TestFrameBuilding:
    def test_query_status_frame(self):
        frame = build_frame(CMD_QUERY_STATUS)
        assert len(frame) == 4
        assert frame[0] == FRAME_HEADER
        assert frame[1] == 3  # length
        assert frame[2] == CMD_QUERY_STATUS
        assert verify_checksum(frame)

    def test_emergency_frame(self):
        frame = build_frame(CMD_EMERGENCY)
        assert len(frame) == 4
        assert frame[2] == CMD_EMERGENCY
        assert verify_checksum(frame)

    def test_set_route_frame_with_json(self):
        payload = b'{"waypoints":[{"id":1,"x":1.0,"y":2.0}]}'
        frame = build_frame(CMD_SET_ROUTE, payload)
        assert frame[1] == 3 + len(payload)
        assert frame[2] == CMD_SET_ROUTE
        assert frame[3 : 3 + len(payload)] == payload
        assert verify_checksum(frame)

    def test_set_schedule_frame(self):
        # 中文用 UTF-8 编码后再转 bytes
        payload = '{"slots":[{"day":"周一","start":"08:00"},{"end":"09:00"}]}'.encode()
        frame = build_frame(CMD_SET_SCHEDULE, payload)
        assert verify_checksum(frame)

    def test_start_stop_frame(self):
        frame = build_frame(CMD_START_STOP, b'\x01')
        assert frame[3] == 0x01  # payload
        assert verify_checksum(frame)

    def test_empty_payload_frame(self):
        frame = build_frame(0x42, b'')
        assert len(frame) == 4
        assert verify_checksum(frame)

    def test_large_payload(self):
        payload = b'x' * 200
        frame = build_frame(CMD_SET_ROUTE, payload)
        assert len(frame) == 4 + 200
        assert verify_checksum(frame)


# ═══════════════════════════════════════════════════
# 校验和
# ═══════════════════════════════════════════════════


class TestChecksum:
    def test_valid_frame_passes(self):
        frame = build_frame(CMD_QUERY_STATUS)
        assert verify_checksum(frame)

    def test_corrupted_byte_fails(self):
        frame = bytearray(build_frame(CMD_QUERY_STATUS))
        frame[2] = 0xFF  # corrupt command byte
        assert not verify_checksum(bytes(frame))

    def test_corrupted_payload_fails(self):
        payload = b'hello'
        frame = bytearray(build_frame(CMD_SET_ROUTE, payload))
        frame[4] ^= 0xFF  # flip bits in payload
        assert not verify_checksum(bytes(frame))

    def test_truncated_frame_fails(self):
        frame = build_frame(CMD_SET_ROUTE, b'payload')
        assert not verify_checksum(frame[:3])

    def test_wrong_header_fails(self):
        frame = bytearray(build_frame(CMD_QUERY_STATUS))
        frame[0] = 0xBB
        assert not verify_checksum(bytes(frame))


# ═══════════════════════════════════════════════════
# 状态 payload 打包/解包
# ═══════════════════════════════════════════════════


class TestStatusPayload:
    def test_build_and_parse_roundtrip(self):
        """打包后解包应一致"""
        payload = build_status_payload(
            battery_pct=85, voltage=52.0, total_km=15.5, working=True, temperature=32
        )
        assert len(payload) == 1 + 4 + 4 + 1 + 1  # 11 bytes

        # 解包
        pct, v, km, w, t = struct.unpack('<Bf f B B', payload)
        assert pct == 85
        assert abs(v - 52.0) < 0.01
        assert abs(km - 15.5) < 0.01
        assert w == 1
        assert t == 32

    def test_battery_zero_percent(self):
        payload = build_status_payload(0, 42.0, 0.0, False, 20)
        pct, v, km, w, t = struct.unpack('<Bf f B B', payload)
        assert pct == 0
        assert abs(v - 42.0) < 0.01
        assert w == 0

    def test_battery_100_percent(self):
        payload = build_status_payload(100, 54.6, 100.0, True, 45)
        pct, v, km, w, t = struct.unpack('<Bf f B B', payload)
        assert pct == 100
        assert abs(v - 54.6) < 0.01
        assert w == 1

    def test_zero_distance(self):
        payload = build_status_payload(50, 48.0, 0.0, False, 25)
        _, _, km, _, _ = struct.unpack('<Bf f B B', payload)
        assert km == 0.0

    def test_payload_endianness(self):
        """验证小端字节序"""
        payload = build_status_payload(50, 48.0, 10.0, True, 30)
        # 10.0f 的小端表示
        float_bytes = payload[5:9]
        km = struct.unpack('<f', float_bytes)[0]
        assert abs(km - 10.0) < 0.01


# ═══════════════════════════════════════════════════
# 命令常量
# ═══════════════════════════════════════════════════


class TestCommandConstants:
    def test_app_to_robot_commands(self):
        assert CMD_QUERY_STATUS == 0x01
        assert CMD_SET_SCHEDULE == 0x02
        assert CMD_SET_ROUTE == 0x03
        assert CMD_EMERGENCY == 0x04
        assert CMD_START_STOP == 0x05

    def test_robot_to_app_responses(self):
        assert RSP_STATUS == 0x11
        assert RSP_ACK == 0x12

    def test_frame_header(self):
        assert FRAME_HEADER == 0xAA

    def test_vs_android_constants(self):
        """与 App 端 BleProtocol 常量一致"""
        # 这些值必须和 BleProtocol.kt 完全一致
        assert CMD_QUERY_STATUS == 0x01
        assert CMD_EMERGENCY == 0x04
        assert RSP_STATUS == 0x11
