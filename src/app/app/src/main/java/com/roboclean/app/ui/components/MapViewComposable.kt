package com.roboclean.app.ui.components

import android.view.MotionEvent
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalLifecycleOwner
import androidx.compose.ui.viewinterop.AndroidView
import androidx.lifecycle.Lifecycle
import androidx.lifecycle.LifecycleEventObserver
import org.osmdroid.config.Configuration
import org.osmdroid.tileprovider.tilesource.TileSourceFactory
import org.osmdroid.util.GeoPoint
import org.osmdroid.views.MapView
import org.osmdroid.views.overlay.Marker
import org.osmdroid.views.overlay.Polyline
import org.osmdroid.views.overlay.compass.CompassOverlay

/**
 * OpenStreetMap 地图组件 (基于 osmdroid)
 *
 * 用法:
 *   OsmMap(
 *     waypoints = listOf(...),
 *     onMapClick = { geoPoint -> ... },
 *     modifier = Modifier
 *   )
 */
@Composable
fun OsmMap(
    waypoints: List<WaypointGeo>,
    onMapClick: ((WaypointGeo) -> Unit)? = null,
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current
    val lifecycle = LocalLifecycleOwner.current.lifecycle

    // 初始化 osmdroid 配置 (仅首次)
    LaunchedEffect(Unit) {
        Configuration.getInstance().apply {
            userAgentValue = context.packageName
            // 可选: 设置离线瓦片缓存目录
            // osmdroid.basePath = context.cacheDir.resolve("osmdroid")
        }
    }

    // 地图 View 引用
    var mapView by remember { mutableStateOf<MapView?>(null) }

    // 生命周期管理 (onResume/onPause)
    DisposableEffect(lifecycle) {
        val observer = LifecycleEventObserver { _, event ->
            when (event) {
                Lifecycle.Event.ON_RESUME -> mapView?.onResume()
                Lifecycle.Event.ON_PAUSE -> mapView?.onPause()
                else -> {}
            }
        }
        lifecycle.addObserver(observer)
        onDispose { lifecycle.removeObserver(observer) }
    }

    // 途经点更新时刷新标记
    LaunchedEffect(waypoints) {
        mapView?.let { updateMarkers(it, waypoints) }
    }

    AndroidView(
        factory = { ctx ->
            MapView(ctx).apply {
                setTileSource(TileSourceFactory.MAPNIK)  // OpenStreetMap 标准瓦片
                setMultiTouchControls(true)
                setBuiltInZoomControls(false)             // 用两根手指缩放

                // 默认位置: 中国中部 (后续可用 GPS 定位)
                controller.setZoom(16.0)
                controller.setCenter(GeoPoint(39.9, 116.4))

                // 指南针
                val compass = CompassOverlay(ctx, this)
                compass.enableCompass()
                overlays.add(compass)

                // 点击地图添加途经点
                setOnTouchListener { _, event ->
                    if (event.action == MotionEvent.ACTION_UP && onMapClick != null) {
                        val gp = projection.fromPixels(
                            event.x.toInt(), event.y.toInt()
                        ) as GeoPoint
                        val idx = (overlays.count { it is Marker }) + 1
                        onMapClick.invoke(
                            WaypointGeo(
                                id = idx,
                                name = "途经点 $idx",
                                lat = gp.latitude,
                                lon = gp.longitude
                            )
                        )
                    }
                    false
                }

                mapView = this
                updateMarkers(this, waypoints)
            }
        },
        modifier = modifier
    )
}

/** 更新地图上的途经点标记和连线 */
private fun updateMarkers(map: MapView, waypoints: List<WaypointGeo>) {
    // 清除旧的标记
    val toRemove = map.overlays.filter { it is Marker || it is Polyline }
    toRemove.forEach { map.overlays.remove(it) }

    val markers = waypoints.map { wp ->
        Marker(map).apply {
            position = GeoPoint(wp.lat, wp.lon)
            setAnchor(Marker.ANCHOR_CENTER, Marker.ANCHOR_BOTTOM)
            title = wp.name
            snippet = "(${String.format("%.6f", wp.lat)}, ${String.format("%.6f", wp.lon)})"
        }
    }
    markers.forEach { map.overlays.add(it) }

    // 连线 (至少2个点)
    if (waypoints.size >= 2) {
        val polyline = Polyline().apply {
            setPoints(waypoints.map { GeoPoint(it.lat, it.lon) })
            outlinePaint.strokeWidth = 6f
            outlinePaint.color = 0x801976D2.toInt()  // Blue700 半透明
        }
        map.overlays.add(polyline)
    }

    map.invalidate()
}

/**
 * 途经点地理数据 — 与 PersistentWaypoint 互补
 */
data class WaypointGeo(
    val id: Int,
    val name: String,
    val lat: Double,
    val lon: Double
)
