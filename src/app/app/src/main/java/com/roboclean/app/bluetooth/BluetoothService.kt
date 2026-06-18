package com.roboclean.app.bluetooth

import android.annotation.SuppressLint
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothSocket
import android.content.Context
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import java.io.InputStream
import java.io.OutputStream
import java.util.UUID

/**
 * 蓝牙 SPP 连接服务
 *
 * ⚠️ 物理依赖:
 *   UUID: 00001101-0000-1000-8000-00805F9B34FB (标准 SPP)
 *   需要定位权限 (Android 12+ 蓝牙扫描要求)
 *   需要 BLUETOOTH_CONNECT 权限
 */
class BluetoothService(private val context: Context) {

    companion object {
        val SPP_UUID: UUID = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB")
    }

    private val adapter: BluetoothAdapter? by lazy {
        val manager = context.getSystemService(android.bluetooth.BluetoothManager::class.java)
        manager.adapter
    }

    private var socket: BluetoothSocket? = null
    private var inputStream: InputStream? = null
    private var outputStream: OutputStream? = null

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    // 状态流
    private val _isConnected = MutableStateFlow(false)
    val isConnected: StateFlow<Boolean> = _isConnected

    private val _robotStatus = MutableStateFlow(RobotStatus(0, 0f, 0f, false, 0))
    val robotStatus: StateFlow<RobotStatus> = _robotStatus

    private val _pairedDevices = MutableStateFlow<List<BluetoothDevice>>(emptyList())
    val pairedDevices: StateFlow<List<BluetoothDevice>> = _pairedDevices

    /**
     * 获取已配对设备列表
     */
    @SuppressLint("MissingPermission")
    fun refreshPairedDevices() {
        val devices = adapter?.bondedDevices?.toList() ?: emptyList()
        _pairedDevices.value = devices
    }

    /**
     * 连接指定设备
     */
    @SuppressLint("MissingPermission")
    fun connect(device: BluetoothDevice) {
        scope.launch {
            try {
                socket = device.createRfcommSocketToServiceRecord(SPP_UUID)
                socket?.connect()
                inputStream = socket?.inputStream
                outputStream = socket?.outputStream
                _isConnected.value = true

                // 启动读取循环
                launch { readLoop() }
                // 启动定时查询
                launch { queryLoop() }
            } catch (e: Exception) {
                _isConnected.value = false
                e.printStackTrace()
            }
        }
    }

    /**
     * 断开连接
     */
    fun disconnect() {
        scope.launch {
            try {
                inputStream?.close()
                outputStream?.close()
                socket?.close()
            } catch (_: Exception) {}
            _isConnected.value = false
        }
    }

    /**
     * 发送查询状态指令
     */
    fun queryStatus() {
        send(BleProtocol.buildFrame(BleProtocol.CMD_QUERY_STATUS))
    }

    /**
     * 发送急停指令
     */
    fun emergencyStop() {
        send(BleProtocol.buildFrame(BleProtocol.CMD_EMERGENCY))
    }

    /**
     * 发送工作时间表
     */
    fun setSchedule(scheduleJson: String) {
        val payload = scheduleJson.toByteArray(Charsets.UTF_8)
        send(BleProtocol.buildFrame(BleProtocol.CMD_SET_SCHEDULE, payload))
    }

    /**
     * 发送路线途经点
     */
    fun setRoute(routeJson: String) {
        val payload = routeJson.toByteArray(Charsets.UTF_8)
        send(BleProtocol.buildFrame(BleProtocol.CMD_SET_ROUTE, payload))
    }

    // ── 内部方法 ──

    private fun send(frame: ByteArray) {
        try {
            outputStream?.write(frame)
            outputStream?.flush()
        } catch (e: Exception) {
            _isConnected.value = false
        }
    }

    private suspend fun readLoop() {
        val buffer = ByteArray(256)
        while (scope.isActive && _isConnected.value) {
            try {
                val bytesRead = withContext(Dispatchers.IO) {
                    inputStream?.read(buffer) ?: -1
                }
                if (bytesRead <= 0) {
                    _isConnected.value = false
                    break
                }
                parseResponse(buffer.copyOf(bytesRead))
            } catch (_: Exception) {
                _isConnected.value = false
                break
            }
        }
    }

    private suspend fun queryLoop() {
        while (scope.isActive && _isConnected.value) {
            queryStatus()
            delay(2000)  // 每2秒查询一次
        }
    }

    private fun parseResponse(data: ByteArray) {
        if (data.isEmpty() || data[0] != BleProtocol.FRAME_HEADER) return
        if (data.size < 4) return

        val length = data[1].toInt() and 0xFF
        val cmd = data[2]
        if (data.size < 3 + length) return
        val payload = data.copyOfRange(3, 3 + length - 3)

        // 校验
        var calc = (BleProtocol.FRAME_HEADER.toInt() xor length xor cmd.toInt()).toByte()
        for (b in payload) calc = (calc.toInt() xor b.toInt()).toByte()
        if (calc != data[3 + length - 3]) return

        when (cmd) {
            BleProtocol.RSP_STATUS -> {
                val status = BleProtocol.parseStatus(payload)
                if (status != null) _robotStatus.value = status
            }
        }
    }

    fun destroy() {
        disconnect()
        scope.cancel()
    }
}
