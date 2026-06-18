package com.roboclean.app.ui.viewmodel

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.roboclean.app.bluetooth.BluetoothService
import com.roboclean.app.data.PersistentWaypoint
import com.roboclean.app.data.RouteRepository
import kotlinx.coroutines.flow.*
import kotlinx.coroutines.launch

/**
 * 路线设置 ViewModel
 *
 * 职责: 途经点增删 + 本地持久化 + 发送到小车
 */
class RouteViewModel(
    private val repository: RouteRepository,
    private val btService: BluetoothService
) : ViewModel() {

    /** 途经点列表 (从 DataStore 加载) */
    val waypoints: StateFlow<List<PersistentWaypoint>> = repository.waypointsFlow
        .stateIn(viewModelScope, SharingStarted.Eagerly, emptyList())

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

    fun addWaypoint(name: String, description: String = "") {
        val current = waypoints.value
        val newId = (current.maxOfOrNull { it.id } ?: 0) + 1
        val updated = current + PersistentWaypoint(id = newId, name = name, description = description)
        save(updated)
    }

    fun deleteWaypoint(id: Int) {
        val updated = waypoints.value.filter { it.id != id }
        save(updated)
    }

    fun save(updated: List<PersistentWaypoint>) {
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
                    kotlinx.serialization.builtins.ListSerializer(PersistentWaypoint.serializer()),
                    waypoints.value
                )
                btService.setRoute(json)
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
