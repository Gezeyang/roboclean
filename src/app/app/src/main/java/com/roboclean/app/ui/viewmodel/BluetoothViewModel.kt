package com.roboclean.app.ui.viewmodel

import android.bluetooth.BluetoothDevice
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.roboclean.app.bluetooth.BluetoothService
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

/**
 * 蓝牙管理 ViewModel
 *
 * 职责: 设备扫描/连接/断开、连接状态展示
 */
class BluetoothViewModel(
    private val btService: BluetoothService
) : ViewModel() {

    /** 连接状态 */
    val isConnected: StateFlow<Boolean> = btService.isConnected
        .stateIn(viewModelScope, SharingStarted.Eagerly, false)

    /** 已配对设备列表 (来自系统蓝牙) */
    val pairedDevices: StateFlow<List<BluetoothDevice>> = btService.pairedDevices
        .stateIn(viewModelScope, SharingStarted.Eagerly, emptyList())

    /** 当前连接的设备名称 */
    private val _connectedDevice = MutableStateFlow<BluetoothDevice?>(null)
    val connectedDevice: StateFlow<BluetoothDevice?> = _connectedDevice

    /** 是否正在扫描 */
    private val _isScanning = MutableStateFlow(false)
    val isScanning: StateFlow<Boolean> = _isScanning

    // ── 操作 ──

    fun startScan() {
        _isScanning.value = true
        btService.refreshPairedDevices()
        // 扫描 6 秒后自动停止
        viewModelScope.launch {
            kotlinx.coroutines.delay(6000)
            _isScanning.value = false
        }
    }

    fun connect(device: BluetoothDevice) {
        _connectedDevice.value = device
        btService.connect(device)
    }

    fun disconnect() {
        btService.disconnect()
        _connectedDevice.value = null
    }
}
