package com.roboclean.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.itemsIndexed
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.roboclean.app.R
import com.roboclean.app.ui.components.OsmMap
import com.roboclean.app.ui.components.WaypointGeo
import com.roboclean.app.ui.theme.*
import com.roboclean.app.ui.viewmodel.RouteViewModel
import androidx.compose.ui.res.stringResource

/**
 * 路线设置页面 — 途经点管理
 */
@Composable
fun RouteScreen(viewModel: RouteViewModel) {
    val waypoints by viewModel.waypoints.collectAsState()
    val uiState by viewModel.uiState.collectAsState()

    var showAddDialog by remember { mutableStateOf(false) }
    var newPointName by remember { mutableStateOf("") }

    // 操作结果反馈
    LaunchedEffect(uiState) {
        when (uiState) {
            is RouteViewModel.UiState.Saved -> viewModel.clearUiState()
            is RouteViewModel.UiState.Sent -> viewModel.clearUiState()
            is RouteViewModel.UiState.Error -> { /* Snackbar 稍后添加 */ }
            else -> {}
        }
    }

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
                    imageVector = Icons.Filled.Route,
                    contentDescription = null,
                    tint = White
                )
                Spacer(modifier = Modifier.width(12.dp))
                Text(
                    text = stringResource(R.string.route_title),
                    style = MaterialTheme.typography.headlineMedium,
                    color = White
                )
            }
        }

        // OpenStreetMap 地图 (osmdroid)
        OsmMap(
            waypoints = waypoints.map { wp ->
                WaypointGeo(
                    id = wp.id,
                    name = wp.name,
                    lat = wp.lat,
                    lon = wp.lon
                )
            },
            onMapClick = { geo ->
                viewModel.addWaypoint(
                    name = geo.name,
                    lat = geo.lat,
                    lon = geo.lon
                )
            },
            modifier = Modifier
                .fillMaxWidth()
                .height(260.dp)
        )

        Spacer(modifier = Modifier.height(8.dp))

        // 途经点列表标题
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 20.dp, vertical = 8.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = stringResource(R.string.waypoint_list_title),
                style = MaterialTheme.typography.titleLarge,
                color = TextPrimary
            )
            if (waypoints.isEmpty()) {
                Text(
                    text = stringResource(R.string.waypoint_empty_hint),
                    style = MaterialTheme.typography.bodyMedium,
                    color = TextHint
                )
            }
        }

        // 途经点列表
        LazyColumn(
            modifier = Modifier.weight(1f),
            contentPadding = PaddingValues(horizontal = 16.dp)
        ) {
            itemsIndexed(waypoints, key = { _, w -> w.id }) { index, waypoint ->
                WaypointItem(
                    index = index + 1,
                    name = waypoint.name,
                    description = waypoint.description,
                    onDelete = { viewModel.deleteWaypoint(waypoint.id) }
                )
            }

            item {
                OutlinedButton(
                    onClick = { showAddDialog = true },
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(vertical = 8.dp),
                    shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.outlinedButtonColors(contentColor = Blue700)
                ) {
                    Icon(Icons.Filled.Add, contentDescription = null)
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(stringResource(R.string.add_waypoint))
                }
            }
        }

        // 底部操作栏
        Surface(
            modifier = Modifier.fillMaxWidth(),
            color = White,
            shadowElevation = 8.dp
        ) {
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(16.dp),
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                OutlinedButton(
                    onClick = { viewModel.save(waypoints) },
                    enabled = uiState !is RouteViewModel.UiState.Saving,
                    modifier = Modifier.weight(1f),
                    shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.outlinedButtonColors(contentColor = Blue700)
                ) {
                    if (uiState is RouteViewModel.UiState.Saving) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(18.dp),
                            strokeWidth = 2.dp,
                            color = Blue700
                        )
                    } else {
                        Icon(Icons.Filled.Save, contentDescription = null, modifier = Modifier.size(18.dp))
                    }
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(stringResource(R.string.save_route))
                }
                Button(
                    onClick = { viewModel.sendToRobot() },
                    enabled = uiState !is RouteViewModel.UiState.Sending && waypoints.isNotEmpty(),
                    modifier = Modifier.weight(1f),
                    shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = Blue700)
                ) {
                    if (uiState is RouteViewModel.UiState.Sending) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(18.dp),
                            strokeWidth = 2.dp,
                            color = White
                        )
                    } else {
                        Icon(Icons.AutoMirrored.Filled.Send, contentDescription = null, modifier = Modifier.size(18.dp))
                    }
                    Spacer(modifier = Modifier.width(6.dp))
                    Text(stringResource(R.string.send_to_car))
                }
            }
        }
    }

    // 添加途经点对话框
    if (showAddDialog) {
        AlertDialog(
            onDismissRequest = { showAddDialog = false },
            title = { Text(stringResource(R.string.add_waypoint), color = Blue800) },
            text = {
                OutlinedTextField(
                    value = newPointName,
                    onValueChange = { newPointName = it },
                    label = { Text(stringResource(R.string.waypoint_name_label)) },
                    singleLine = true,
                    modifier = Modifier.fillMaxWidth(),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = Blue500,
                        focusedLabelColor = Blue700
                    )
                )
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        if (newPointName.isNotBlank()) {
                            viewModel.addWaypoint(newPointName.trim())
                            newPointName = ""
                            showAddDialog = false
                        }
                    },
                    colors = ButtonDefaults.textButtonColors(contentColor = Blue700)
                ) { Text("确定") }
            },
            dismissButton = {
                TextButton(onClick = { showAddDialog = false }) {
                    Text(stringResource(R.string.cancel), color = TextSecondary)
                }
            }
        )
    }
}

@Composable
fun WaypointItem(
    index: Int,
    name: String,
    description: String,
    onDelete: () -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(containerColor = GrayBg),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier
                    .size(32.dp)
                    .background(Blue700, RoundedCornerShape(8.dp)),
                contentAlignment = Alignment.Center
            ) {
                Text(
                    text = "$index",
                    color = White,
                    fontWeight = FontWeight.Bold,
                    fontSize = 14.sp
                )
            }

            Spacer(modifier = Modifier.width(12.dp))

            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = name,
                    style = MaterialTheme.typography.titleMedium,
                    color = TextPrimary
                )
                if (description.isNotBlank()) {
                    Text(
                        text = description,
                        style = MaterialTheme.typography.bodyMedium,
                        color = TextSecondary
                    )
                }
            }

            Icon(
                imageVector = Icons.Filled.DragHandle,
                contentDescription = "拖拽排序",
                tint = TextHint,
                modifier = Modifier.size(24.dp)
            )

            Spacer(modifier = Modifier.width(8.dp))

            IconButton(
                onClick = onDelete,
                modifier = Modifier.size(32.dp)
            ) {
                Icon(
                    imageVector = Icons.Filled.Delete,
                    contentDescription = "删除",
                    tint = Error,
                    modifier = Modifier.size(20.dp)
                )
            }
        }
    }
}
