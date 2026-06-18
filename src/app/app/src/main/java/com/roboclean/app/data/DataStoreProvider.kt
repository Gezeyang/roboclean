package com.roboclean.app.data

import android.content.Context
import androidx.datastore.core.DataStore
import androidx.datastore.preferences.core.Preferences
import androidx.datastore.preferences.preferencesDataStore

/**
 * 单例 DataStore，全局共享
 */
val Context.dataStore: DataStore<Preferences> by preferencesDataStore(name = "roboclean_prefs")
