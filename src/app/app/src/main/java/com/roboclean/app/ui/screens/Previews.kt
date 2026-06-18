package com.roboclean.app.ui.screens

import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.tooling.preview.Preview
import androidx.compose.ui.unit.dp
import com.roboclean.app.bluetooth.RobotStatus
import com.roboclean.app.ui.theme.*

/**
 * 集中管理所有 Screen 和组件的 @Preview
 */
@Preview(name = "Dashboard - Light", showBackground = true, group = "Dashboard")
@Preview(name = "Dashboard - Dark", showBackground = true, uiMode = android.content.res.Configuration.UI_MODE_NIGHT_YES, group = "Dashboard")
@Composable
private fun DashboardScreenPreview() {
    RoboCleanTheme {
        DashboardScreenPreviewContent()
    }
}

@Composable
private fun DashboardScreenPreviewContent() {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .padding(16.dp),
        horizontalAlignment = androidx.compose.ui.Alignment.CenterHorizontally
    ) {
        BatteryRing(level = 78, modifier = Modifier.size(160.dp))
        Spacer(modifier = Modifier.height(16.dp))
        InfoCard(icon = "📏", title = "累计行驶", value = "12.8 km", modifier = Modifier.fillMaxWidth())
        Spacer(modifier = Modifier.height(12.dp))
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            StatusCard(label = "连接状态", value = "已连接", color = Success, modifier = Modifier.weight(1f))
            StatusCard(label = "工作状态", value = "工作中", color = Blue500, modifier = Modifier.weight(1f))
        }
    }
}

@Preview(name = "BatteryRing - High", showBackground = true, group = "Components")
@Preview(name = "BatteryRing - Low", showBackground = true, group = "Components")
@Composable
private fun BatteryRingPreviews() {
    RoboCleanTheme {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(16.dp)) {
            BatteryRing(level = 85, modifier = Modifier.size(160.dp))
            BatteryRing(level = 25, modifier = Modifier.size(160.dp))
            BatteryRing(level = 8, modifier = Modifier.size(160.dp))
        }
    }
}

@Preview(name = "DeviceCard - Available", showBackground = true, group = "Bluetooth")
@Preview(name = "DeviceCard - Connected", showBackground = true, group = "Bluetooth")
@Composable
private fun DeviceCardPreviews() {
    RoboCleanTheme {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            // 假设备 — Preview only
            // DeviceCard precondition: needs android.bluetooth.BluetoothDevice
            Box(modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
                contentAlignment = androidx.compose.ui.Alignment.Center
            ) {
                Text("DeviceCard Preview 需真机/模拟器",
                    style = MaterialTheme.typography.bodyMedium,
                    color = TextHint)
            }
        }
    }
}

@Preview(name = "WaypointItem", showBackground = true, group = "Route")
@Composable
private fun WaypointItemPreview() {
    RoboCleanTheme {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            WaypointItem(index = 1, name = "饲喂通道A起点", description = "靠近围栏入口处", onDelete = {})
            WaypointItem(index = 2, name = "饲喂通道A终点", description = "", onDelete = {})
        }
    }
}

@Preview(name = "TimeSlotItem", showBackground = true, group = "Schedule")
@Composable
private fun TimeSlotItemPreview() {
    RoboCleanTheme {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            TimeSlotItem(8, 0, 9, 30, enabled = true, onToggle = {}, onDelete = {})
            TimeSlotItem(14, 0, 16, 0, enabled = false, onToggle = {}, onDelete = {})
        }
    }
}

@Preview(name = "StatusCard - Connected", showBackground = true, group = "Components")
@Composable
private fun StatusCardConnectedPreview() {
    RoboCleanTheme {
        StatusCard(label = "连接状态", value = "已连接", color = Success)
    }
}
