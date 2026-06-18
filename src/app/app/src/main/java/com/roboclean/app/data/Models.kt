package com.roboclean.app.data

import kotlinx.serialization.Serializable

/**
 * 可持久化的途经点 (含地理坐标)
 */
@Serializable
data class PersistentWaypoint(
    val id: Int,
    val name: String,
    val description: String = "",
    val lat: Double = 0.0,   // 纬度
    val lon: Double = 0.0    // 经度
)

/**
 * 可持久化的时间段
 */
@Serializable
data class PersistentTimeSlot(
    val id: Int,
    val dayOfWeek: String,
    val startHour: Int,
    val startMinute: Int,
    val endHour: Int,
    val endMinute: Int,
    val enabled: Boolean = true
)
