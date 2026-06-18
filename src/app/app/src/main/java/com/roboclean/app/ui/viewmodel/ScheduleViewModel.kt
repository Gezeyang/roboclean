package com.roboclean.app.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.roboclean.app.bluetooth.BluetoothService
import com.roboclean.app.data.PersistentTimeSlot
import com.roboclean.app.data.ScheduleRepository
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch

/**
 * 工作时间设置 ViewModel
 *
 * 职责: 时间段增删改 + 启用/禁用 + 本地持久化 + 发送到小车
 */
class ScheduleViewModel(
    private val repository: ScheduleRepository,
    private val btService: BluetoothService
) : ViewModel() {

    /** 时间段列表 (从 DataStore 加载) */
    val timeSlots: StateFlow<List<PersistentTimeSlot>> = repository.slotsFlow
        .stateIn(viewModelScope, SharingStarted.Eagerly, emptyList())

    /** 按星期分组 */
    val groupedByDay: StateFlow<Map<String, List<PersistentTimeSlot>>> = timeSlots
        .map { slots -> slots.groupBy { it.dayOfWeek } }
        .stateIn(viewModelScope, SharingStarted.Eagerly, emptyMap())

    /** 操作状态 */
    sealed class UiState {
        object Idle : UiState()
        object Saving : UiState()
        object Sending : UiState()
        data class Error(val message: String) : UiState()
        object Saved : UiState()
        object Sent : UiState()
    }

    private val _uiState = MutableStateFlow<UiState>(UiState.Idle)
    val uiState: StateFlow<UiState> = _uiState

    // ── 操作 ──

    fun addTimeSlot(
        dayOfWeek: String,
        startHour: Int,
        startMinute: Int,
        endHour: Int,
        endMinute: Int
    ) {
        // 输入校验
        val sh = startHour.coerceIn(0, 23)
        val sm = startMinute.coerceIn(0, 59)
        val eh = endHour.coerceIn(0, 23)
        val em = endMinute.coerceIn(0, 59)

        val current = timeSlots.value
        val newId = (current.maxOfOrNull { it.id } ?: 0) + 1
        val updated = current + PersistentTimeSlot(
            id = newId,
            dayOfWeek = dayOfWeek,
            startHour = sh, startMinute = sm,
            endHour = eh, endMinute = em,
            enabled = true
        )
        save(updated)
    }

    fun toggleSlot(id: Int) {
        val updated = timeSlots.value.map {
            if (it.id == id) it.copy(enabled = !it.enabled) else it
        }
        save(updated)
    }

    fun deleteSlot(id: Int) {
        val updated = timeSlots.value.filter { it.id != id }
        save(updated)
    }

    fun save(updated: List<PersistentTimeSlot>) {
        viewModelScope.launch {
            _uiState.value = UiState.Saving
            try {
                repository.save(updated)
                _uiState.value = UiState.Saved
            } catch (e: Exception) {
                _uiState.value = UiState.Error("保存失败: ${e.message}")
            }
        }
    }

    fun sendToRobot() {
        viewModelScope.launch {
            _uiState.value = UiState.Sending
            try {
                val json = kotlinx.serialization.json.Json.encodeToString(
                    kotlinx.serialization.builtins.ListSerializer(PersistentTimeSlot.serializer()),
                    timeSlots.value
                )
                btService.setSchedule(json)
                _uiState.value = UiState.Sent
            } catch (e: Exception) {
                _uiState.value = UiState.Error("发送失败: ${e.message}")
            }
        }
    }

    fun clearUiState() {
        _uiState.value = UiState.Idle
    }
}
