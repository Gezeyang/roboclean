package com.roboclean.app.ui.viewmodel

import androidx.lifecycle.ViewModel
import com.roboclean.app.bluetooth.BluetoothService
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.flow.asStateFlow
import androidx.lifecycle.viewModelScope

class ControlViewModel(
    private val btService: BluetoothService
) : ViewModel() {

    val isConnected: StateFlow<Boolean> = btService.isConnected
        .stateIn(viewModelScope, SharingStarted.Eagerly, false)

    /** 当前速度档位: 0 = 慢 (0.15 m/s), 1 = 快 (0.30 m/s) */
    private val _speedLevel = MutableStateFlow(0)
    val speedLevel: StateFlow<Int> = _speedLevel.asStateFlow()

    /** 刷子是否开启 */
    private val _brushOn = MutableStateFlow(false)
    val brushOn: StateFlow<Boolean> = _brushOn.asStateFlow()

    fun toggleSpeed() {
        _speedLevel.value = (_speedLevel.value + 1) % 2
    }

    val currentSpeed: Float
        get() = if (_speedLevel.value == 0) 0.15f else 0.30f

    val speedLabel: String
        get() = if (_speedLevel.value == 0) "慢速 0.15 m/s" else "快速 0.30 m/s"

    // ── 操控 ──

    fun moveForward() {
        btService.sendManualControl(
            """{"action":"move","direction":"forward","speed":$currentSpeed}"""
        )
    }

    fun moveBackward() {
        btService.sendManualControl(
            """{"action":"move","direction":"backward","speed":${currentSpeed * 0.5f}}"""
        )
    }

    fun turnLeft() {
        btService.sendManualControl(
            """{"action":"move","direction":"left","speed":$currentSpeed}"""
        )
    }

    fun turnRight() {
        btService.sendManualControl(
            """{"action":"move","direction":"right","speed":$currentSpeed}"""
        )
    }

    fun stop() {
        btService.sendManualControl("""{"action":"stop"}""")
    }

    fun toggleBrush() {
        _brushOn.value = !_brushOn.value
        btService.sendManualControl(
            """{"action":"brush","on":${_brushOn.value}}"""
        )
    }

    fun emergencyStop() {
        btService.emergencyStop()
    }

    // ── 路径录制 / 回放 ──

    private val _isRecording = MutableStateFlow(false)
    val isRecording: StateFlow<Boolean> = _isRecording.asStateFlow()

    private val _isPlaying = MutableStateFlow(false)
    val isPlaying: StateFlow<Boolean> = _isPlaying.asStateFlow()

    fun startRecording() {
        _isRecording.value = true
        btService.sendManualControl("""{"action":"record_start","name":"示教路径"}""")
    }

    fun stopRecording() {
        _isRecording.value = false
        btService.sendManualControl("""{"action":"record_stop"}""")
    }

    fun startPlayback() {
        _isPlaying.value = true
        btService.sendManualControl("""{"action":"playback_start","file":""}""")
    }

    fun stopPlayback() {
        _isPlaying.value = false
        btService.sendManualControl("""{"action":"playback_stop"}""")
    }
}
