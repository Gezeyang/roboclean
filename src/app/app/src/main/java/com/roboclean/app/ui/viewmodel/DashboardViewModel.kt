package com.roboclean.app.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.roboclean.app.bluetooth.BluetoothService
import com.roboclean.app.bluetooth.RobotStatus
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn

/**
 * 仪表盘 ViewModel
 *
 * 职责: 汇聚机器人状态 + 快捷操作 (急停/回充/启停)
 */
class DashboardViewModel(
    private val btService: BluetoothService
) : ViewModel() {

    /** 机器人状态 (来自蓝牙) */
    val robotStatus: StateFlow<RobotStatus> = btService.robotStatus
        .stateIn(viewModelScope, SharingStarted.Eagerly, RobotStatus(0, 0f, 0f, false, 0))

    /** 蓝牙连接状态 */
    val isConnected: StateFlow<Boolean> = btService.isConnected
        .stateIn(viewModelScope, SharingStarted.Eagerly, false)

    /**
     * 预计剩余工作时间 (小时)
     *
     * 公式: 剩余容量(Ah) / 平均电流(A)
     *  剩余容量 = 60Ah * batteryPercent/100
     *  平均电流 ≈ (500W×2 + 200W) / 48V ≈ 25A (满载)
     *            ≈ 15A (平均负载, 推料状态)
     *  实际值装车后需校准
     */
    fun estimatedHours(): String {
        val status = robotStatus.value
        val capacityAh = 60.0                              // 电池 60Ah
        val avgCurrentA = 15.0                             // 平均工作电流 ≈ 15A
        val hours = (capacityAh * status.batteryPercent / 100.0) / avgCurrentA
        return "%.1f 小时".format(hours.coerceAtLeast(0.0))
    }

    // ── 操作 ──

    fun emergencyStop() {
        btService.emergencyStop()
    }

    fun returnToCharge() {
        // TODO(2026-06-18): 发送回充指令 — 需小车端 charging_dock 完成
        btService.setRoute("{\"cmd\":\"return_to_charge\"}")
    }

    fun toggleStartStop() {
        // TODO(2026-06-18): 实现启停切换 — 需确认协议 0x05 的 payload 格式
        btService.queryStatus()
    }
}
