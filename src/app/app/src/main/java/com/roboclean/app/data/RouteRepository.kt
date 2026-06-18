package com.roboclean.app.data

import android.content.Context
import androidx.datastore.preferences.core.edit
import androidx.datastore.preferences.core.stringPreferencesKey
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.map
import kotlinx.serialization.encodeToString
import kotlinx.serialization.json.Json

class RouteRepository(context: Context) {

    private val dataStore = context.dataStore

    companion object {
        private val KEY_WAYPOINTS = stringPreferencesKey("waypoints")
        private val json = Json { ignoreUnknownKeys = true }
    }

    /** 获取途经点流 */
    val waypointsFlow: Flow<List<PersistentWaypoint>> = dataStore.data.map { prefs ->
        val raw = prefs[KEY_WAYPOINTS] ?: return@map emptyList()
        try { json.decodeFromString<List<PersistentWaypoint>>(raw) }
        catch (_: Exception) { emptyList() }
    }

    /** 保存途经点列表 */
    suspend fun save(waypoints: List<PersistentWaypoint>) {
        dataStore.edit { prefs ->
            prefs[KEY_WAYPOINTS] = json.encodeToString(waypoints)
        }
    }
}
