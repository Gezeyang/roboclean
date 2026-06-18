package com.roboclean.app.data

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json

class ScheduleRepository(context: Context) {

    private val dataStore = context.dataStore

    companion object {
        private val KEY_SLOTS = stringPreferencesKey("timeslots")
        private val json = Json { ignoreUnknownKeys = true }
    }

    /** 获取时间段流 */
    val slotsFlow: Flow<List<PersistentTimeSlot>> = dataStore.data.map { prefs ->
        val raw = prefs[KEY_SLOTS] ?: return@map emptyList()
        try { json.decodeFromString<List<PersistentTimeSlot>>(raw) }
        catch (_: Exception) { emptyList() }
    }

    /** 保存时间段列表 */
    suspend fun save(slots: List<PersistentTimeSlot>) {
        dataStore.edit { prefs ->
            prefs[KEY_SLOTS] = json.encodeToString(slots)
        }
    }
}
