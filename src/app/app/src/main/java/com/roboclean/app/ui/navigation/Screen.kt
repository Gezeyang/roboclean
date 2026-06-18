package com.roboclean.app.ui.navigation

import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Bluetooth
import androidx.compose.material.icons.filled.Dashboard
import androidx.compose.material.icons.filled.Gamepad
import androidx.compose.material.icons.filled.Route
import androidx.compose.material.icons.filled.Schedule
import androidx.compose.ui.graphics.vector.ImageVector

sealed class Screen(
    val route: String,
    val label: String,
    val icon: ImageVector
) {
    data object Dashboard : Screen("dashboard", "仪表盘", Icons.Filled.Dashboard)
    data object Route : Screen("route", "路线", Icons.Filled.Route)
    data object Schedule : Screen("schedule", "时间", Icons.Filled.Schedule)
    data object Control : Screen("control", "操控", Icons.Filled.Gamepad)
    data object Bluetooth : Screen("bluetooth", "蓝牙", Icons.Filled.Bluetooth)

    companion object {
        val items = listOf(Dashboard, Route, Schedule, Control, Bluetooth)
    }
}
