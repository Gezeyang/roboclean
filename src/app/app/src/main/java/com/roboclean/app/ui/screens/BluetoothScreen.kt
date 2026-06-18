package com.roboclean.app.ui.screens

import android.bluetooth.BluetoothDevice
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.roboclean.app.R
import com.roboclean.app.ui.theme.*
import com.roboclean.app.ui.viewmodel.BluetoothViewModel
import androidx.compose.ui.res.stringResource

/**
 * 蓝牙管理页面 — 使用真实 BluetoothService
 */
@Composable
fun BluetoothScreen(viewModel: BluetoothViewModel) {
    val isConnected by viewModel.isConnected.collectAsState()
    val pairedDevices by viewModel.pairedDevices.collectAsState()
    val connectedDevice by viewModel.connectedDevice.collectAsState()
    val isScanning by viewModel.isScanning.collectAsState()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(White)
    ) {
        // 顶部标题栏
        Surface(
            modifier = Modifier.fillMaxWidth(),
            color = Blue800,
            shadowElevation = 4.dp
        ) {
            Row(
                modifier = Modifier
                    .padding(horizontal = 16.dp, vertical = 16.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Icon(
                    imageVector = Icons.Filled.Bluetooth,
                    contentDescription = null,
                    tint = White
                )
                Spacer(modifier = Modifier.width(12.dp))
                Text(
                    text = stringResource(R.string.bluetooth_title),
                    style = MaterialTheme.typography.headlineMedium,
                    color = White
                )
            }
        }

        LazyColumn(
            modifier = Modifier.fillMaxSize(),
            contentPadding = PaddingValues(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            // 已连接设备
            item {
                Text(
                    text = stringResource(R.string.connected_devices),
                    style = MaterialTheme.typography.titleMedium,
                    color = Success,
                    modifier = Modifier.padding(vertical = 8.dp)
                )
            }

            item {
                if (isConnected && connectedDevice != null) {
                    DeviceCard(
                        device = connectedDevice!!,
                        isConnected = true,
                        onDisconnect = { viewModel.disconnect() }
                    )
                } else {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(16.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = stringResource(R.string.no_device_connected),
                            style = MaterialTheme.typography.bodyMedium,
                            color = TextHint
                        )
                    }
                }
            }

            // 可用设备
            item {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 8.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = stringResource(R.string.available_devices),
                        style = MaterialTheme.typography.titleMedium,
                        color = TextPrimary
                    )
                    TextButton(
                        onClick = { viewModel.startScan() },
                        colors = ButtonDefaults.textButtonColors(contentColor = Blue700)
                    ) {
                        Icon(
                            Icons.Filled.Refresh,
                            contentDescription = null,
                            modifier = Modifier.size(18.dp)
                        )
                        Spacer(modifier = Modifier.width(4.dp))
                        Text(stringResource(R.string.scan_refresh))
                    }
                }
            }

            if (isScanning) {
                item {
                    LinearProgressIndicator(
                        modifier = Modifier.fillMaxWidth(),
                        color = Blue500,
                        trackColor = Blue50
                    )
                }
            }

            // 过滤掉已连接的设备
            val availableDevices = pairedDevices.filter { it.address != connectedDevice?.address }
            if (availableDevices.isEmpty() && !isScanning) {
                item {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(24.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = stringResource(R.string.no_device_found),
                            style = MaterialTheme.typography.bodyMedium,
                            color = TextHint
                        )
                    }
                }
            }

            items(availableDevices, key = { it.address }) { device ->
                DeviceCard(
                    device = device,
                    isConnected = false,
                    onConnect = { viewModel.connect(device) }
                )
            }

            // 说明文字
            item {
                Spacer(modifier = Modifier.height(24.dp))
                Card(
                    modifier = Modifier.fillMaxWidth(),
                    shape = RoundedCornerShape(12.dp),
                    colors = CardDefaults.cardColors(containerColor = Blue50)
                ) {
                    Row(
                        modifier = Modifier.padding(16.dp),
                        verticalAlignment = Alignment.Top
                    ) {
                        Icon(
                            Icons.Filled.Info,
                            contentDescription = null,
                            tint = Blue500,
                            modifier = Modifier.size(20.dp)
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Column {
                            Text(
                                text = "提示",
                                style = MaterialTheme.typography.titleMedium,
                                color = Blue800
                            )
                            Text(
                                text = stringResource(R.string.bt_tip_content),
                                style = MaterialTheme.typography.bodyMedium,
                                color = Blue700
                            )
                        }
                    }
                }
            }
        }
    }
}

// ─── 设备卡片组件 ───

@Composable
fun DeviceCard(
    device: BluetoothDevice,
    isConnected: Boolean,
    onConnect: (() -> Unit)? = null,
    onDisconnect: (() -> Unit)? = null
) {
    Card(
        modifier = Modifier.fillMaxWidth(),
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(
            containerColor = if (isConnected) Blue50 else GrayBg
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = if (isConnected) 2.dp else 0.dp)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier
                    .size(44.dp)
                    .clip(CircleShape)
                    .background(if (isConnected) Success else Blue100),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    Icons.Filled.Bluetooth,
                    contentDescription = null,
                    tint = if (isConnected) White else Blue500,
                    modifier = Modifier.size(24.dp)
                )
            }

            Spacer(modifier = Modifier.width(12.dp))

            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = device.name ?: "未知设备",
                    style = MaterialTheme.typography.titleMedium,
                    color = TextPrimary
                )
                Spacer(modifier = Modifier.height(2.dp))
                Text(
                    text = device.address,
                    style = MaterialTheme.typography.bodyMedium,
                    color = TextSecondary
                )
            }

            if (isConnected) {
                Button(
                    onClick = { onDisconnect?.invoke() },
                    colors = ButtonDefaults.buttonColors(
                        containerColor = Error,
                        contentColor = White
                    ),
                    shape = RoundedCornerShape(8.dp)
                ) {
                    Text(stringResource(R.string.bt_disconnect), fontSize = 14.sp)
                }
            } else {
                Button(
                    onClick = { onConnect?.invoke() },
                    colors = ButtonDefaults.buttonColors(
                        containerColor = Blue700,
                        contentColor = White
                    ),
                    shape = RoundedCornerShape(8.dp)
                ) {
                    Text(stringResource(R.string.bt_connect), fontSize = 14.sp)
                }
            }
        }
    }
}
