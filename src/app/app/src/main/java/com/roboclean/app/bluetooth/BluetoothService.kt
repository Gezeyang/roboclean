package com.roboclean.app.bluetooth

import android.annotation.SuppressLint
import android.bluetooth.BluetoothAdapter
import android.bluetooth.BluetoothDevice
import android.bluetooth.BluetoothManager
import android.bluetooth.BluetoothSocket
import android.content.BroadcastReceiver
import android.content.Context
import android.content.Intent
import android.content.IntentFilter
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import java.io.InputStream
import java.io.OutputStream
import java.util.UUID

/**
 * 蓝牙 SPP 连接服务 — 发现 + 配对 + 连接 + 通信
 */
class BluetoothService(private val context: Context) {

    companion object {
        val SPP_UUID: UUID = UUID.fromString("00001101-0000-1000-8000-00805F9B34FB")
        private const val SCAN_TIMEOUT_MS = 12_000L  // 扫描超时 12 秒
    }

    private val adapter: BluetoothAdapter? by lazy {
        val manager = context.getSystemService(android.bluetooth.BluetoothManager::class.java)
        manager.adapter
    }

    private var socket: BluetoothSocket? = null
    private var inputStream: InputStream? = null
    private var outputStream: OutputStream? = null

    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    // ── 状态流 ──

    private val _isConnected = MutableStateFlow(false)
    val isConnected: StateFlow<Boolean> = _isConnected

    private val _robotStatus = MutableStateFlow(RobotStatus(0, 0f, 0f, false, 0))
    val robotStatus: StateFlow<RobotStatus> = _robotStatus

    /** 已配对设备 */
    private val _pairedDevices = MutableStateFlow<List<BluetoothDevice>>(emptyList())
    val pairedDevices: StateFlow<List<BluetoothDevice>> = _pairedDevices

    /** 扫描发现的新设备 */
    private val _discoveredDevices = MutableStateFlow<List<BluetoothDevice>>(emptyList())
    val discoveredDevices: StateFlow<List<BluetoothDevice>> = _discoveredDevices

    /** 是否正在扫描 */
    private val _isScanning = MutableStateFlow(false)
    val isScanning: StateFlow<Boolean> = _isScanning

    // ── 广播接收器 ──

    private val discoveryReceiver = object : BroadcastReceiver() {
        @SuppressLint("MissingPermission")
        override fun onReceive(context: Context?, intent: Intent?) {
            when (intent?.action) {
                BluetoothDevice.ACTION_FOUND -> {
                    @Suppress("DEPRECATION")
                    val device: BluetoothDevice? =
                        intent.getParcelableExtra(BluetoothDevice.EXTRA_DEVICE)
                    if (device != null && device.name != null) {
                        val current = _discoveredDevices.value.toMutableList()
                        if (current.none { it.address == device.address }) {
                            current.add(device)
                            _discoveredDevices.value = current
                        }
                    }
                }
                BluetoothAdapter.ACTION_DISCOVERY_FINISHED -> {
                    _isScanning.value = false
                }
            }
        }
    }

    init {
        val filter = IntentFilter().apply {
            addAction(BluetoothDevice.ACTION_FOUND)
            addAction(BluetoothAdapter.ACTION_DISCOVERY_FINISHED)
        }
        context.registerReceiver(discoveryReceiver, filter)
    }

    // ── 设备发现 ──

    /** 开始扫描附近蓝牙设备 */
    @SuppressLint("MissingPermission")
    fun startDiscovery() {
        val bt = adapter ?: return
        if (bt.isDiscovering) bt.cancelDiscovery()

        _discoveredDevices.value = emptyList()
        _isScanning.value = true

        bt.startDiscovery()

        // 超时自动停止
        scope.launch {
            delay(SCAN_TIMEOUT_MS)
            if (bt.isDiscovering) {
                bt.cancelDiscovery()
                _isScanning.value = false
            }
        }
    }

    /** 停止扫描 */
    @SuppressLint("MissingPermission")
    fun cancelDiscovery() {
        adapter?.cancelDiscovery()
        _isScanning.value = false
    }

    /** 获取已配对设备列表 */
    @SuppressLint("MissingPermission")
    fun refreshPairedDevices() {
        val devices = adapter?.bondedDevices?.toList() ?: emptyList()
        _pairedDevices.value = devices
    }

    // ── 连接 / 断连 ──

    @SuppressLint("MissingPermission")
    fun connect(device: BluetoothDevice) {
        cancelDiscovery()
        scope.launch {
            try {
                socket = device.createRfcommSocketToServiceRecord(SPP_UUID)
                socket?.connect()
                inputStream = socket?.inputStream
                outputStream = socket?.outputStream
                _isConnected.value = true

                launch { readLoop() }
                launch { queryLoop() }
            } catch (e: Exception) {
                _isConnected.value = false
                e.printStackTrace()
            }
        }
    }

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

    // ── 指令 ──

    fun queryStatus() {
        send(BleProtocol.buildFrame(BleProtocol.CMD_QUERY_STATUS))
    }

    fun emergencyStop() {
        send(BleProtocol.buildFrame(BleProtocol.CMD_EMERGENCY))
    }

    fun setSchedule(scheduleJson: String) {
        val payload = scheduleJson.toByteArray(Charsets.UTF_8)
        send(BleProtocol.buildFrame(BleProtocol.CMD_SET_SCHEDULE, payload))
    }

    fun setRoute(routeJson: String) {
        val payload = routeJson.toByteArray(Charsets.UTF_8)
        send(BleProtocol.buildFrame(BleProtocol.CMD_SET_ROUTE, payload))
    }

    // ── 内部 ──

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
            delay(2000)
        }
    }

    private fun parseResponse(data: ByteArray) {
        if (data.isEmpty() || data[0] != BleProtocol.FRAME_HEADER) return
        if (data.size < 4) return
        val length = data[1].toInt() and 0xFF
        val cmd = data[2]
        if (data.size < 3 + length) return
        val payload = data.copyOfRange(3, 3 + length - 3)
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
        cancelDiscovery()
        try { context.unregisterReceiver(discoveryReceiver) } catch (_: Exception) {}
        disconnect()
        scope.cancel()
    }
}
