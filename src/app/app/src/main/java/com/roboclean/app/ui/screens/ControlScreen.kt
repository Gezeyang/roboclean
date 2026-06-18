package com.roboclean.app.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.roboclean.app.ui.theme.*
import com.roboclean.app.ui.viewmodel.ControlViewModel

@Composable
fun ControlScreen(viewModel: ControlViewModel) {
    val isConnected by viewModel.isConnected.collectAsState()
    val speedLevel by viewModel.speedLevel.collectAsState()
    val brushOn by viewModel.brushOn.collectAsState()

    // 方向控制状态
    var activeDir by remember { mutableStateOf("") }

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
                modifier = Modifier.padding(horizontal = 16.dp, vertical = 16.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Icon(Icons.Filled.Gamepad, contentDescription = null, tint = White)
                Spacer(modifier = Modifier.width(12.dp))
                Column {
                    Text("手动操控", style = MaterialTheme.typography.headlineMedium, color = White)
                    Text(
                        text = if (isConnected) "已连接" else "未连接 — 操控不可用",
                        fontSize = 12.sp,
                        color = if (isConnected) White.copy(alpha = 0.7f) else Error
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(24.dp))

        // ── 十字方向键 ──
        Column(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 24.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            // 前进
            ControlButton(
                text = "▲ 前进",
                color = Blue500,
                isActive = activeDir == "forward",
                enabled = isConnected,
                onClick = {
                    if (activeDir == "forward") { viewModel.stop(); activeDir = "" }
                    else { viewModel.moveForward(); activeDir = "forward" }
                },
                modifier = Modifier.fillMaxWidth(0.5f).height(64.dp)
            )

            Spacer(modifier = Modifier.height(12.dp))

            Row(
                modifier = Modifier.fillMaxWidth(0.85f),
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                ControlButton(
                    text = "◄ 左转",
                    color = Blue500,
                    isActive = activeDir == "left",
                    enabled = isConnected,
                    onClick = {
                        if (activeDir == "left") { viewModel.stop(); activeDir = "" }
                        else { viewModel.turnLeft(); activeDir = "left" }
                    },
                    modifier = Modifier.weight(1f).height(64.dp)
                )

                // 停止
                Button(
                    onClick = { viewModel.stop(); activeDir = "" },
                    modifier = Modifier.weight(1f).height(64.dp),
                    enabled = isConnected,
                    colors = ButtonDefaults.buttonColors(containerColor = Error, contentColor = White),
                    shape = RoundedCornerShape(16.dp)
                ) {
                    Text("■ 停止", fontSize = 18.sp, fontWeight = FontWeight.Bold)
                }

                ControlButton(
                    text = "右转 ►",
                    color = Blue500,
                    isActive = activeDir == "right",
                    enabled = isConnected,
                    onClick = {
                        if (activeDir == "right") { viewModel.stop(); activeDir = "" }
                        else { viewModel.turnRight(); activeDir = "right" }
                    },
                    modifier = Modifier.weight(1f).height(64.dp)
                )
            }

            Spacer(modifier = Modifier.height(12.dp))

            ControlButton(
                text = "▼ 后退",
                color = Blue500,
                isActive = activeDir == "backward",
                enabled = isConnected,
                onClick = {
                    if (activeDir == "backward") { viewModel.stop(); activeDir = "" }
                    else { viewModel.moveBackward(); activeDir = "backward" }
                },
                modifier = Modifier.fillMaxWidth(0.5f).height(64.dp)
            )
        }

        Spacer(modifier = Modifier.height(24.dp))

        // ── 速度切换 ──
        Row(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 24.dp),
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Button(
                onClick = { viewModel.toggleSpeed() },
                modifier = Modifier.weight(1f).height(52.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = if (speedLevel == 0) Blue500 else Warning
                ),
                shape = RoundedCornerShape(12.dp)
            ) {
                Text(viewModel.speedLabel, fontSize = 16.sp)
            }

            Button(
                onClick = { viewModel.toggleBrush() },
                modifier = Modifier.weight(1f).height(52.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = if (brushOn) Success else GrayCard,
                    contentColor = if (brushOn) White else TextSecondary
                ),
                shape = RoundedCornerShape(12.dp)
            ) {
                Icon(Icons.Filled.CleaningServices, contentDescription = null, modifier = Modifier.size(20.dp))
                Spacer(modifier = Modifier.width(6.dp))
                Text(if (brushOn) "刷子: 开" else "刷子: 关", fontSize = 16.sp)
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        // ── 路径录制 / 回放 ──
        val isRecording by viewModel.isRecording.collectAsState()
        val isPlaying by viewModel.isPlaying.collectAsState()

        Row(
            modifier = Modifier.fillMaxWidth().padding(horizontal = 24.dp),
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Button(
                onClick = { if (isRecording) viewModel.stopRecording() else viewModel.startRecording() },
                modifier = Modifier.weight(1f).height(48.dp),
                colors = ButtonDefaults.buttonColors(
                    containerColor = if (isRecording) Error else Blue500
                ),
                shape = RoundedCornerShape(12.dp)
            ) {
                Icon(
                    if (isRecording) Icons.Filled.Stop else Icons.Filled.Circle,
                    contentDescription = null, modifier = Modifier.size(18.dp)
                )
                Spacer(modifier = Modifier.width(4.dp))
                Text(if (isRecording) "停止录制" else "开始录制", fontSize = 14.sp)
            }

            Button(
                onClick = { if (isPlaying) viewModel.stopPlayback() else viewModel.startPlayback() },
                modifier = Modifier.weight(1f).height(48.dp),
                enabled = !isRecording,
                colors = ButtonDefaults.buttonColors(
                    containerColor = if (isPlaying) Warning else Blue700
                ),
                shape = RoundedCornerShape(12.dp)
            ) {
                Icon(
                    if (isPlaying) Icons.Filled.Stop else Icons.Filled.PlayArrow,
                    contentDescription = null, modifier = Modifier.size(18.dp)
                )
                Spacer(modifier = Modifier.width(4.dp))
                Text(if (isPlaying) "停止回放" else "开始回放", fontSize = 14.sp)
            }
        }

        Spacer(modifier = Modifier.weight(1f))

        // ── 紧急停止 ──
        Button(
            onClick = { viewModel.emergencyStop(); activeDir = "" },
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 24.dp)
                .height(72.dp),
            colors = ButtonDefaults.buttonColors(containerColor = Error, contentColor = White),
            shape = RoundedCornerShape(16.dp)
        ) {
            Icon(Icons.Filled.Warning, contentDescription = null, modifier = Modifier.size(32.dp))
            Spacer(modifier = Modifier.width(10.dp))
            Text("🛑 紧急停止", fontSize = 24.sp, fontWeight = FontWeight.Bold)
        }

        Spacer(modifier = Modifier.height(8.dp))
        Text(
            text = "再次点击方向按钮可停止",
            style = MaterialTheme.typography.bodyMedium,
            color = TextHint,
            modifier = Modifier.align(Alignment.CenterHorizontally).padding(bottom = 16.dp)
        )
    }
}

@Composable
private fun ControlButton(
    text: String,
    color: androidx.compose.ui.graphics.Color,
    isActive: Boolean,
    enabled: Boolean,
    onClick: () -> Unit,
    modifier: Modifier = Modifier
) {
    Button(
        onClick = onClick,
        modifier = modifier,
        enabled = enabled,
        colors = ButtonDefaults.buttonColors(
            containerColor = if (isActive) color else color.copy(alpha = 0.15f),
            contentColor = if (isActive) White else color,
            disabledContainerColor = GrayCard,
            disabledContentColor = TextHint
        ),
        shape = RoundedCornerShape(16.dp)
    ) {
        Text(text, fontSize = 18.sp, fontWeight = FontWeight.Bold)
    }
}
