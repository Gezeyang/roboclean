package com.roboclean.app.data

import kotlinx.serialization.Serializable

/**
 * 可持久化的途经点
 */
@Serializable
data class PersistentWaypoint(
    val id: Int,
    val name: String,
    val description: String = ""
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
