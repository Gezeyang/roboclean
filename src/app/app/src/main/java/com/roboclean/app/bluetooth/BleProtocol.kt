package com.roboclean.app.bluetooth

/**
 * 蓝牙通信协议 — 与小车端 bt_server.py 对齐
 *
 * ⚠️ 物理依赖:
 *   蓝牙名称: RoboClean-001 (可通过 App 扫描修改)
 *   通信距离: ~10m
 *   帧格式必须与小车端一致，否则无法通信
 *
 * 帧: [0xAA] [长度] [指令] [数据...] [异或校验]
 */
object BleProtocol {
    const val FRAME_HEADER: Byte = 0xAA.toByte()

    // App → 小车
    const val CMD_QUERY_STATUS: Byte = 0x01
    const val CMD_SET_SCHEDULE: Byte = 0x02
    const val CMD_SET_ROUTE: Byte    = 0x03
    const val CMD_EMERGENCY: Byte    = 0x04
    const val CMD_START_STOP: Byte   = 0x05

    // 小车 → App
    const val RSP_STATUS: Byte = 0x11
    const val RSP_ACK: Byte    = 0x12

    /**
     * 构建发送帧
     */
    fun buildFrame(cmd: Byte, payload: ByteArray = ByteArray(0)): ByteArray {
        val length = (3 + payload.size).toByte()
        var checksum = (FRAME_HEADER.toInt() xor length.toInt() xor cmd.toInt()).toByte()
        for (b in payload) checksum = (checksum.toInt() xor b.toInt()).toByte()

        val frame = ByteArray(4 + payload.size)
        frame[0] = FRAME_HEADER
        frame[1] = length
        frame[2] = cmd
        payload.copyInto(frame, 3)
        frame[frame.lastIndex] = checksum
        return frame
    }

    /**
     * 解析状态响应帧 → RobotStatus
     */
    fun parseStatus(payload: ByteArray): RobotStatus? {
        // B=uint8 f=float32 B=uint8 B=uint8 = 1+4+4+1+1 = 11 bytes
        if (payload.size < 11) return null
        val batteryPct = payload[0].toInt() and 0xFF
        val batteryV   = java.nio.ByteBuffer.wrap(payload, 1, 4).order(java.nio.ByteOrder.LITTLE_ENDIAN).float
        val totalKm    = java.nio.ByteBuffer.wrap(payload, 5, 4).order(java.nio.ByteOrder.LITTLE_ENDIAN).float
        val working    = payload[9].toInt() != 0
        val temp       = payload[10].toInt() and 0xFF
        return RobotStatus(batteryPct, batteryV, totalKm, working, temp)
    }
}

data class RobotStatus(
    val batteryPercent: Int,
    val batteryVoltage: Float,
    val totalKm: Float,
    val isWorking: Boolean,
    val temperature: Int
)
