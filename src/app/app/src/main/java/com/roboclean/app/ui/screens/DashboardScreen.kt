package com.roboclean.app.ui.screens

import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.tooling.preview.Preview
import com.roboclean.app.R
import com.roboclean.app.ui.theme.*
import com.roboclean.app.ui.viewmodel.DashboardViewModel
import androidx.compose.ui.res.stringResource

/**
 * 仪表盘主页 — 电量、里程、连接状态、工作状态
 */
@Composable
fun DashboardScreen(viewModel: DashboardViewModel) {
    val robotStatus by viewModel.robotStatus.collectAsState()
    val isConnected by viewModel.isConnected.collectAsState()

    // 工作状态推导
    val isWorking = robotStatus.isWorking
    val estimatedTime = viewModel.estimatedHours()

    Column(
        modifier = Modifier
            .fillMaxSize()
            .background(White)
            .verticalScroll(rememberScrollState())
            .padding(horizontal = 20.dp, vertical = 24.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        // 顶部标题
        Text(
            text = stringResource(R.string.dashboard_title),
            style = MaterialTheme.typography.headlineLarge,
            color = Blue800
        )
        Spacer(modifier = Modifier.height(8.dp))
        Text(
            text = if (isConnected) stringResource(R.string.device_online) else stringResource(R.string.device_offline),
            style = MaterialTheme.typography.bodyMedium,
            color = if (isConnected) Success else Error
        )

        Spacer(modifier = Modifier.height(32.dp))

        // 电量环形图
        BatteryRing(
            level = robotStatus.batteryPercent,
            modifier = Modifier.size(180.dp)
        )
        Spacer(modifier = Modifier.height(8.dp))
        Text(
            text = stringResource(R.string.estimated_work_time, estimatedTime),
            style = MaterialTheme.typography.bodyMedium,
            color = TextSecondary
        )

        Spacer(modifier = Modifier.height(28.dp))

        // 里程卡片
        InfoCard(
            icon = "📏",
            title = stringResource(R.string.total_mileage),
            value = "${"%.1f".format(robotStatus.totalKm)} km",
            modifier = Modifier.fillMaxWidth()
        )

        Spacer(modifier = Modifier.height(16.dp))

        // 状态行：两个卡片并排
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            StatusCard(
                label = stringResource(R.string.connection_status),
                value = if (isConnected) stringResource(R.string.connected) else stringResource(R.string.disconnected),
                color = if (isConnected) Success else Error,
                modifier = Modifier.weight(1f)
            )
            StatusCard(
                label = stringResource(R.string.work_status),
                value = if (isWorking) stringResource(R.string.working) else stringResource(R.string.idle),
                color = if (isWorking) Blue500 else TextSecondary,
                modifier = Modifier.weight(1f)
            )
        }

        Spacer(modifier = Modifier.height(16.dp))

        // 快捷操作按钮
        Row(
            modifier = Modifier.fillMaxWidth(),
            horizontalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            OutlinedButton(
                onClick = { viewModel.returnToCharge() },
                modifier = Modifier.weight(1f),
                colors = ButtonDefaults.outlinedButtonColors(contentColor = Warning),
                shape = RoundedCornerShape(12.dp)
            ) {
                Text(stringResource(R.string.return_to_charge))
            }

            Button(
                onClick = { viewModel.emergencyStop() },
                modifier = Modifier.weight(1f),
                colors = ButtonDefaults.buttonColors(
                    containerColor = Error,
                    contentColor = White
                ),
                shape = RoundedCornerShape(12.dp)
            ) {
                Text(stringResource(R.string.emergency_stop))
            }
        }
    }
}

// ─── 电量环形组件 ───

@Composable
fun BatteryRing(
    level: Int,
    modifier: Modifier = Modifier
) {
    val sweepAngle = level / 100f * 270f
    val ringColor = when {
        level > 50 -> BatteryGreen
        level > 20 -> BatteryOrange
        else -> BatteryRed
    }

    Box(modifier = modifier, contentAlignment = Alignment.Center) {
        Canvas(modifier = Modifier.fillMaxSize()) {
            val strokeWidth = 16.dp.toPx()
            val padding = strokeWidth / 2
            drawArc(
                color = GrayCard,
                startAngle = 135f,
                sweepAngle = 270f,
                useCenter = false,
                topLeft = Offset(padding, padding),
                size = Size(size.width - strokeWidth, size.height - strokeWidth),
                style = Stroke(width = strokeWidth, cap = StrokeCap.Round)
            )
            drawArc(
                color = ringColor,
                startAngle = 135f,
                sweepAngle = sweepAngle,
                useCenter = false,
                topLeft = Offset(padding, padding),
                size = Size(size.width - strokeWidth, size.height - strokeWidth),
                style = Stroke(width = strokeWidth, cap = StrokeCap.Round)
            )
        }

        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text(
                text = "$level%",
                fontSize = 32.sp,
                fontWeight = FontWeight.Bold,
                color = ringColor
            )
            Text(
                text = "🔋",
                fontSize = 20.sp
            )
        }
    }
}

// ─── 信息卡片组件 ───

@Composable
fun InfoCard(
    icon: String,
    title: String,
    value: String,
    modifier: Modifier = Modifier
) {
    Card(
        modifier = modifier,
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = GrayBg),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(20.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(text = icon, fontSize = 28.sp)
            Spacer(modifier = Modifier.width(16.dp))
            Column {
                Text(
                    text = title,
                    style = MaterialTheme.typography.bodyMedium,
                    color = TextSecondary
                )
                Text(
                    text = value,
                    style = MaterialTheme.typography.headlineMedium,
                    color = TextPrimary
                )
            }
        }
    }
}

// ─── 状态卡片组件 ───

@Composable
fun StatusCard(
    label: String,
    value: String,
    color: Color,
    modifier: Modifier = Modifier
) {
    Card(
        modifier = modifier,
        shape = RoundedCornerShape(16.dp),
        colors = CardDefaults.cardColors(containerColor = GrayBg),
        elevation = CardDefaults.cardElevation(defaultElevation = 0.dp)
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            horizontalAlignment = Alignment.CenterHorizontally
        ) {
            Box(
                modifier = Modifier
                    .size(12.dp)
                    .clip(CircleShape)
                    .background(color)
            )
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = label,
                style = MaterialTheme.typography.bodyMedium,
                color = TextSecondary
            )
            Text(
                text = value,
                style = MaterialTheme.typography.titleMedium,
                color = color
            )
        }
    }
}
