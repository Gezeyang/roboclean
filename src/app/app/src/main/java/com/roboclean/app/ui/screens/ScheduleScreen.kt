package com.roboclean.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.KeyboardType
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.roboclean.app.R
import com.roboclean.app.ui.theme.*
import com.roboclean.app.ui.viewmodel.ScheduleViewModel
import androidx.compose.ui.res.stringResource

/**
 * 工作时间设置页面 — 时间段管理
 */
@Composable
fun ScheduleScreen(viewModel: ScheduleViewModel) {
    val timeSlots by viewModel.timeSlots.collectAsState()
    val groupedByDay by viewModel.groupedByDay.collectAsState()
    val uiState by viewModel.uiState.collectAsState()

    val weekDays = listOf("周一", "周二", "周三", "周四", "周五", "周六", "周日")

    // 当前选中的星期筛选（null = 全部）
    var selectedDayFilter by remember { mutableStateOf<String?>(null) }

    var showAddDialog by remember { mutableStateOf(false) }
    var addDay by remember { mutableStateOf("周一") }

    // 操作结果反馈
    LaunchedEffect(uiState) {
        when (uiState) {
            is ScheduleViewModel.UiState.Saved -> viewModel.clearUiState()
            is ScheduleViewModel.UiState.Sent -> viewModel.clearUiState()
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
                    imageVector = Icons.Filled.Schedule,
                    contentDescription = null,
                    tint = White
                )
                Spacer(modifier = Modifier.width(12.dp))
                Text(
                    text = stringResource(R.string.schedule_title),
                    style = MaterialTheme.typography.headlineMedium,
                    color = White
                )
            }
        }

        // 星期筛选行
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 12.dp, vertical = 8.dp),
            horizontalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            // "全部" 芯片
            FilterChip(
                selected = selectedDayFilter == null,
                onClick = { selectedDayFilter = null },
                label = {
                    Text(
                        "全部",
                        fontSize = 12.sp,
                        color = if (selectedDayFilter == null) White else TextSecondary
                    )
                },
                colors = FilterChipDefaults.filterChipColors(
                    selectedContainerColor = Blue700,
                    containerColor = GrayBg
                )
            )
            weekDays.forEach { day ->
                val hasSlots = groupedByDay.containsKey(day)
                FilterChip(
                    selected = selectedDayFilter == day,
                    onClick = { selectedDayFilter = if (selectedDayFilter == day) null else day },
                    label = {
                        Text(
                            day,
                            fontSize = 12.sp,
                            color = if (selectedDayFilter == day) White
                                    else if (hasSlots) Blue700
                                    else TextSecondary
                        )
                    },
                    colors = FilterChipDefaults.filterChipColors(
                        selectedContainerColor = Blue500,
                        containerColor = GrayBg
                    )
                )
            }
        }

        // 时间段列表
        LazyColumn(
            modifier = Modifier.weight(1f),
            contentPadding = PaddingValues(horizontal = 16.dp, vertical = 8.dp)
        ) {
            val displayDays = if (selectedDayFilter != null)
                listOf(selectedDayFilter!!)
            else
                weekDays

            displayDays.forEach { day ->
                val slots = groupedByDay[day] ?: emptyList()
                if (slots.isNotEmpty() || selectedDayFilter != null) {
                    item {
                        Text(
                            text = day,
                            style = MaterialTheme.typography.titleMedium,
                            color = Blue700,
                            modifier = Modifier.padding(vertical = 8.dp)
                        )
                    }
                    items(slots, key = { it.id }) { slot ->
                        TimeSlotItem(
                            startHour = slot.startHour,
                            startMinute = slot.startMinute,
                            endHour = slot.endHour,
                            endMinute = slot.endMinute,
                            enabled = slot.enabled,
                            onToggle = { viewModel.toggleSlot(slot.id) },
                            onDelete = { viewModel.deleteSlot(slot.id) }
                        )
                    }
                }
            }

            if (timeSlots.isEmpty()) {
                item {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(32.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Icon(
                                Icons.Filled.Schedule,
                                contentDescription = null,
                                modifier = Modifier.size(48.dp),
                                tint = TextHint
                            )
                            Spacer(modifier = Modifier.height(8.dp))
                            Text(
                                text = "尚未设置工作时间",
                                style = MaterialTheme.typography.bodyMedium,
                                color = TextHint
                            )
                        }
                    }
                }
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
                    Text("添加时间段")
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
                    onClick = { viewModel.save(timeSlots) },
                    enabled = uiState !is ScheduleViewModel.UiState.Saving,
                    modifier = Modifier.weight(1f),
                    shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.outlinedButtonColors(contentColor = Blue700)
                ) {
                    if (uiState is ScheduleViewModel.UiState.Saving) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(18.dp), strokeWidth = 2.dp, color = Blue700
                        )
                    } else {
                        Icon(Icons.Filled.Save, contentDescription = null, modifier = Modifier.size(18.dp))
                    }
                    Spacer(modifier = Modifier.width(6.dp))
                    Text("保存")
                }
                Button(
                    onClick = { viewModel.sendToRobot() },
                    enabled = uiState !is ScheduleViewModel.UiState.Sending && timeSlots.isNotEmpty(),
                    modifier = Modifier.weight(1f),
                    shape = RoundedCornerShape(12.dp),
                    colors = ButtonDefaults.buttonColors(containerColor = Blue700)
                ) {
                    if (uiState is ScheduleViewModel.UiState.Sending) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(18.dp), strokeWidth = 2.dp, color = White
                        )
                    } else {
                        Icon(Icons.AutoMirrored.Filled.Send, contentDescription = null, modifier = Modifier.size(18.dp))
                    }
                    Spacer(modifier = Modifier.width(6.dp))
                    Text("发送到小车")
                }
            }
        }
    }

    // 添加时间段对话框
    if (showAddDialog) {
        var hourStart by remember { mutableStateOf("08") }
        var minStart by remember { mutableStateOf("00") }
        var hourEnd by remember { mutableStateOf("09") }
        var minEnd by remember { mutableStateOf("00") }

        // 输入校验
        fun validInput(): Boolean {
            val hs = hourStart.toIntOrNull() ?: return false
            val ms = minStart.toIntOrNull() ?: return false
            val he = hourEnd.toIntOrNull() ?: return false
            val me = minEnd.toIntOrNull() ?: return false
            if (hs !in 0..23 || he !in 0..23 || ms !in 0..59 || me !in 0..59) return false
            // 结束时间必须晚于开始时间
            val startMin = hs * 60 + ms
            val endMin = he * 60 + me
            return endMin > startMin
        }

        AlertDialog(
            onDismissRequest = { showAddDialog = false },
            title = { Text("添加工作时间", color = Blue800) },
            text = {
                Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
                    Text("选择星期", style = MaterialTheme.typography.bodyMedium)
                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        weekDays.forEach { day ->
                            FilterChip(
                                selected = addDay == day,
                                onClick = { addDay = day },
                                label = { Text(day, fontSize = 12.sp) },
                                colors = FilterChipDefaults.filterChipColors(
                                    selectedContainerColor = Blue500
                                )
                            )
                        }
                    }

                    HorizontalDivider()

                    Text("开始时间", style = MaterialTheme.typography.bodyMedium)
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        OutlinedTextField(
                            value = hourStart,
                            onValueChange = { if (it.length <= 2) hourStart = it },
                            modifier = Modifier.width(70.dp),
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                            singleLine = true,
                            isError = (hourStart.toIntOrNull() ?: 0) !in 0..23,
                            colors = OutlinedTextFieldDefaults.colors(focusedBorderColor = Blue500)
                        )
                        Text(":", fontSize = 20.sp, fontWeight = FontWeight.Bold)
                        OutlinedTextField(
                            value = minStart,
                            onValueChange = { if (it.length <= 2) minStart = it },
                            modifier = Modifier.width(70.dp),
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                            singleLine = true,
                            isError = (minStart.toIntOrNull() ?: 0) !in 0..59,
                            colors = OutlinedTextFieldDefaults.colors(focusedBorderColor = Blue500)
                        )
                    }

                    Text("结束时间", style = MaterialTheme.typography.bodyMedium)
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        OutlinedTextField(
                            value = hourEnd,
                            onValueChange = { if (it.length <= 2) hourEnd = it },
                            modifier = Modifier.width(70.dp),
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                            singleLine = true,
                            isError = (hourEnd.toIntOrNull() ?: 0) !in 0..23,
                            colors = OutlinedTextFieldDefaults.colors(focusedBorderColor = Blue500)
                        )
                        Text(":", fontSize = 20.sp, fontWeight = FontWeight.Bold)
                        OutlinedTextField(
                            value = minEnd,
                            onValueChange = { if (it.length <= 2) minEnd = it },
                            modifier = Modifier.width(70.dp),
                            keyboardOptions = KeyboardOptions(keyboardType = KeyboardType.Number),
                            singleLine = true,
                            isError = (minEnd.toIntOrNull() ?: 0) !in 0..59,
                            colors = OutlinedTextFieldDefaults.colors(focusedBorderColor = Blue500)
                        )
                    }

                    if (!validInput() && (hourStart.isNotEmpty() || hourEnd.isNotEmpty())) {
                        Text(
                            text = "请输入有效时间 (00:00-23:59)，结束时间需晚于开始时间",
                            style = MaterialTheme.typography.bodyMedium,
                            color = Error
                        )
                    }
                }
            },
            confirmButton = {
                TextButton(
                    onClick = {
                        if (validInput()) {
                            viewModel.addTimeSlot(
                                dayOfWeek = addDay,
                                startHour = hourStart.toInt(),
                                startMinute = minStart.toInt(),
                                endHour = hourEnd.toInt(),
                                endMinute = minEnd.toInt()
                            )
                            showAddDialog = false
                        }
                    },
                    enabled = validInput(),
                    colors = ButtonDefaults.textButtonColors(contentColor = Blue700)
                ) { Text("确定") }
            },
            dismissButton = {
                TextButton(onClick = { showAddDialog = false }) {
                    Text("取消", color = TextSecondary)
                }
            }
        )
    }
}

@Composable
fun TimeSlotItem(
    startHour: Int,
    startMinute: Int,
    endHour: Int,
    endMinute: Int,
    enabled: Boolean,
    onToggle: () -> Unit,
    onDelete: () -> Unit
) {
    Card(
        modifier = Modifier
            .fillMaxWidth()
            .padding(vertical = 4.dp),
        shape = RoundedCornerShape(12.dp),
        colors = CardDefaults.cardColors(
            containerColor = if (enabled) Blue50 else GrayBg
        ),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "${"%02d".format(startHour)}:${"%02d".format(startMinute)}",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
                color = if (enabled) Blue800 else TextHint
            )
            Text(
                text = " — ",
                style = MaterialTheme.typography.bodyLarge,
                color = TextSecondary
            )
            Text(
                text = "${"%02d".format(endHour)}:${"%02d".format(endMinute)}",
                style = MaterialTheme.typography.titleLarge,
                fontWeight = FontWeight.Bold,
                color = if (enabled) Blue800 else TextHint
            )

            Spacer(modifier = Modifier.weight(1f))

            Switch(
                checked = enabled,
                onCheckedChange = { onToggle() },
                colors = SwitchDefaults.colors(
                    checkedThumbColor = White,
                    checkedTrackColor = Blue500,
                    uncheckedTrackColor = GrayCard
                )
            )

            Spacer(modifier = Modifier.width(4.dp))

            IconButton(onClick = onDelete, modifier = Modifier.size(32.dp)) {
                Icon(
                    Icons.Filled.Delete,
                    contentDescription = "删除",
                    tint = Error,
                    modifier = Modifier.size(20.dp)
                )
            }
        }
    }
}
