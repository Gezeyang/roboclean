package com.roboclean.app.ui.viewmodel

import android.bluetooth.BluetoothDevice
import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.roboclean.app.bluetooth.BluetoothService
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn

class BluetoothViewModel(
    private val btService: BluetoothService
) : ViewModel() {

    val isConnected: StateFlow<Boolean> = btService.isConnected
        .stateIn(viewModelScope, SharingStarted.Eagerly, false)

    /** 已配对设备 (Android 系统蓝牙) */
    val pairedDevices: StateFlow<List<BluetoothDevice>> = btService.pairedDevices
        .stateIn(viewModelScope, SharingStarted.Eagerly, emptyList())

    /** 扫描发现的设备 */
    val discoveredDevices: StateFlow<List<BluetoothDevice>> = btService.discoveredDevices
        .stateIn(viewModelScope, SharingStarted.Eagerly, emptyList())

    /** 是否正在扫描 */
    val isScanning: StateFlow<Boolean> = btService.isScanning
        .stateIn(viewModelScope, SharingStarted.Eagerly, false)

    /** 当前连接的设备 */
    private val _connectedDevice = MutableStateFlow<BluetoothDevice?>(null)
    val connectedDevice: StateFlow<BluetoothDevice?> = _connectedDevice

    /** 所有可用设备 = 已配对 + 新发现 (去重) */
    val allDevices: StateFlow<List<BluetoothDevice>> = btService.discoveredDevices
        .stateIn(viewModelScope, SharingStarted.Eagerly, emptyList())

    fun startScan() {
        btService.refreshPairedDevices()
        btService.startDiscovery()
    }

    fun cancelScan() {
        btService.cancelDiscovery()
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
