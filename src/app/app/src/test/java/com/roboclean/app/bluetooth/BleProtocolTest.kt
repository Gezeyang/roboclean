package com.roboclean.app.bluetooth

import org.junit.Assert.*
import org.junit.Test

/**
 * 蓝牙协议层单元测试
 *
 * 目标覆盖率: ≥90%
 * 测试内容: 帧构造、校验和计算、状态解析、边界条件
 */
class BleProtocolTest {

    // ═══════════════════════════════════════════════════
    // buildFrame — 帧构造
    // ═══════════════════════════════════════════════════

    @Test
    fun `buildFrame with empty payload produces correct structure`() {
        val frame = BleProtocol.buildFrame(cmd = 0x01, payload = ByteArray(0))

        assertEquals(0xAA.toByte(), frame[0])                // header
        assertEquals(3.toByte(), frame[1])                    // length = 3 + 0
        assertEquals(0x01.toByte(), frame[2])                 // cmd
        assertEquals(4, frame.size)                            // 4 bytes total
        // checksum = 0xAA ^ 0x03 ^ 0x01 = 0xA8
        assertEquals((0xAA xor 0x03 xor 0x01).toByte(), frame[3])
    }

    @Test
    fun `buildFrame with payload produces correct checksum`() {
        val payload = byteArrayOf(0x10, 0x20, 0x30)
        val frame = BleProtocol.buildFrame(cmd = 0x02, payload = payload)

        assertEquals(0xAA.toByte(), frame[0])
        assertEquals(6.toByte(), frame[1])                    // 3 + 3 = 6
        assertEquals(0x02.toByte(), frame[2])
        assertArrayEquals(payload, frame.copyOfRange(3, 6))
        // checksum = 0xAA ^ 0x06 ^ 0x02 ^ 0x10 ^ 0x20 ^ 0x30 = 0x8E
        val expected: Byte = (0xAA xor 0x06 xor 0x02 xor 0x10 xor 0x20 xor 0x30).toByte()
        assertEquals(expected, frame[6])
    }

    @Test
    fun `buildFrame for emergency stop has no payload`() {
        val frame = BleProtocol.buildFrame(BleProtocol.CMD_EMERGENCY)

        assertEquals(3.toByte(), frame[1])                    // length = 3
        assertEquals(0x04.toByte(), frame[2])
    }

    @Test
    fun `buildFrame with single byte payload`() {
        val frame = BleProtocol.buildFrame(cmd = 0x05, payload = byteArrayOf(0x01))

        assertEquals(4.toByte(), frame[1])                    // 3 + 1 = 4
        assertEquals(0x01.toByte(), frame[3])                 // payload
    }

    @Test
    fun `buildFrame with large payload`() {
        val payload = ByteArray(200) { it.toByte() }
        val frame = BleProtocol.buildFrame(cmd = 0x03, payload = payload)

        assertEquals((203).toByte(), frame[1])                // 3 + 200
        assertEquals(payload[199], frame[202])                 // last payload byte
    }

    @Test
    fun `buildFrame checksum is consistent for identical inputs`() {
        val f1 = BleProtocol.buildFrame(0x01, byteArrayOf(0x42))
        val f2 = BleProtocol.buildFrame(0x01, byteArrayOf(0x42))
        assertArrayEquals(f1, f2)
    }

    // ═══════════════════════════════════════════════════
    // parseStatus — 状态解析
    // ═══════════════════════════════════════════════════

    @Test
    fun `parseStatus with full payload returns correct data`() {
        // B=78, f=52.0, f=12.8, B=1, B=35
        val payload = ByteArray(11)
        payload[0] = 78                        // battery%
        // voltage 52.0f LE
        java.nio.ByteBuffer.wrap(payload, 1, 4)
            .order(java.nio.ByteOrder.LITTLE_ENDIAN)
            .putFloat(52.0f)
        // totalKm 12.8f LE
        java.nio.ByteBuffer.wrap(payload, 5, 4)
            .order(java.nio.ByteOrder.LITTLE_ENDIAN)
            .putFloat(12.8f)
        payload[9] = 1                         // working = true
        payload[10] = 35                       // temp = 35°C

        val status = BleProtocol.parseStatus(payload)

        assertNotNull(status)
        assertEquals(78, status!!.batteryPercent)
        assertEquals(52.0f, status.batteryVoltage)
        assertEquals(12.8f, status.totalKm)
        assertTrue(status.isWorking)
        assertEquals(35, status.temperature)
    }

    @Test
    fun `parseStatus with too short payload returns null`() {
        val payload = ByteArray(10)  // need 11
        val result = BleProtocol.parseStatus(payload)
        assertNull(result)
    }

    @Test
    fun `parseStatus with empty payload returns null`() {
        val result = BleProtocol.parseStatus(ByteArray(0))
        assertNull(result)
    }

    @Test
    fun `parseStatus with battery at 0 percent`() {
        val payload = ByteArray(11)
        payload[0] = 0
        payload[9] = 0
        payload[10] = 20

        val status = BleProtocol.parseStatus(payload)
        assertNotNull(status)
        assertEquals(0, status!!.batteryPercent)
        assertFalse(status.isWorking)
    }

    @Test
    fun `parseStatus with battery at 100 percent`() {
        val payload = ByteArray(11)
        // 255 = 0xFF → parse as unsigned byte = 255
        payload[0] = 100.toByte()
        payload[9] = 1
        payload[10] = 40

        val status = BleProtocol.parseStatus(payload)
        assertNotNull(status)
        assertEquals(100, status!!.batteryPercent)
    }

    @Test
    fun `parseStatus working flag false when byte is zero`() {
        val payload = ByteArray(11)
        payload[9] = 0  // working = false
        payload[10] = 25

        val status = BleProtocol.parseStatus(payload)
        assertNotNull(status)
        assertFalse(status!!.isWorking)
    }

    @Test
    fun `parseStatus temperature zero degrees`() {
        val payload = ByteArray(11)
        payload[10] = 0

        val status = BleProtocol.parseStatus(payload)
        assertNotNull(status)
        assertEquals(0, status!!.temperature)
    }

    // ═══════════════════════════════════════════════════
    // 命令常量
    // ═══════════════════════════════════════════════════

    @Test
    fun `command constants match protocol specification`() {
        assertEquals(0x01.toByte(), BleProtocol.CMD_QUERY_STATUS)
        assertEquals(0x02.toByte(), BleProtocol.CMD_SET_SCHEDULE)
        assertEquals(0x03.toByte(), BleProtocol.CMD_SET_ROUTE)
        assertEquals(0x04.toByte(), BleProtocol.CMD_EMERGENCY)
        assertEquals(0x05.toByte(), BleProtocol.CMD_START_STOP)
        assertEquals(0x11.toByte(), BleProtocol.RSP_STATUS)
        assertEquals(0x12.toByte(), BleProtocol.RSP_ACK)
    }
}
