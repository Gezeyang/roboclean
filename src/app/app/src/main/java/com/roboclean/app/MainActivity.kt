package com.roboclean.app

import android.os.Bundle
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.enableEdgeToEdge
import androidx.compose.foundation.layout.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.unit.dp
import androidx.lifecycle.viewmodel.compose.viewModel
import androidx.navigation.NavGraph.Companion.findStartDestination
import androidx.navigation.compose.NavHost
import androidx.navigation.compose.composable
import androidx.navigation.compose.currentBackStackEntryAsState
import androidx.navigation.compose.rememberNavController
import com.roboclean.app.bluetooth.BluetoothService
import com.roboclean.app.data.RouteRepository
import com.roboclean.app.data.ScheduleRepository
import com.roboclean.app.ui.navigation.Screen
import com.roboclean.app.ui.screens.*
import com.roboclean.app.ui.screens.*
import com.roboclean.app.ui.theme.*
import com.roboclean.app.ui.viewmodel.*

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        enableEdgeToEdge()
        setContent {
            RoboCleanTheme {
                MainApp()
            }
        }
    }
}

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun MainApp() {
    val context = LocalContext.current

    // 顶层共享服务
    val btService = remember { BluetoothService(context) }

    // ViewModels — 在 NavHost 外层创建，所有 Screen 共享
    val dashboardVM: DashboardViewModel = viewModel(
        factory = ViewModelFactory { DashboardViewModel(btService) }
    )
    val bluetoothVM: BluetoothViewModel = viewModel(
        factory = ViewModelFactory { BluetoothViewModel(btService) }
    )
    val routeRepo = remember { RouteRepository(context) }
    val routeVM: RouteViewModel = viewModel(
        factory = ViewModelFactory { RouteViewModel(routeRepo, btService) }
    )
    val scheduleRepo = remember { ScheduleRepository(context) }
    val scheduleVM: ScheduleViewModel = viewModel(
        factory = ViewModelFactory { ScheduleViewModel(scheduleRepo, btService) }
    )
    val controlVM: ControlViewModel = viewModel(
        factory = ViewModelFactory { ControlViewModel(btService) }
    )

    DisposableEffect(Unit) {
        onDispose { btService.destroy() }
    }

    val navController = rememberNavController()
    val navBackStackEntry by navController.currentBackStackEntryAsState()
    val currentRoute = navBackStackEntry?.destination?.route

    Scaffold(
        modifier = Modifier.fillMaxSize(),
        containerColor = White,
        bottomBar = {
            if (currentRoute in Screen.items.map { it.route }) {
                NavigationBar(
                    containerColor = White,
                    tonalElevation = 4.dp
                ) {
                    Screen.items.forEach { screen ->
                        val selected = currentRoute == screen.route
                        NavigationBarItem(
                            icon = {
                                Icon(
                                    imageVector = screen.icon,
                                    contentDescription = screen.label
                                )
                            },
                            label = { Text(screen.label) },
                            selected = selected,
                            onClick = {
                                navController.navigate(screen.route) {
                                    popUpTo(navController.graph.findStartDestination().id) {
                                        saveState = true
                                    }
                                    launchSingleTop = true
                                    restoreState = true
                                }
                            },
                            colors = NavigationBarItemDefaults.colors(
                                selectedIconColor = Blue700,
                                selectedTextColor = Blue700,
                                unselectedIconColor = TextSecondary,
                                unselectedTextColor = TextSecondary,
                                indicatorColor = Blue50
                            )
                        )
                    }
                }
            }
        }
    ) { innerPadding ->
        NavHost(
            navController = navController,
            startDestination = Screen.Dashboard.route,
            modifier = Modifier.padding(innerPadding)
        ) {
            composable(Screen.Dashboard.route) {
                DashboardScreen(viewModel = dashboardVM)
            }
            composable(Screen.Route.route) {
                RouteScreen(viewModel = routeVM)
            }
            composable(Screen.Schedule.route) {
                ScheduleScreen(viewModel = scheduleVM)
            }
            composable(Screen.Control.route) {
                ControlScreen(viewModel = controlVM)
            }
            composable(Screen.Bluetooth.route) {
                BluetoothScreen(viewModel = bluetoothVM)
            }
        }
    }
}

/**
 * 简易 ViewModel Factory — 避免引入 Hilt/Koin 等 DI 框架
 */
class ViewModelFactory<T : androidx.lifecycle.ViewModel>(
    private val create: () -> T
) : androidx.lifecycle.ViewModelProvider.Factory {
    @Suppress("UNCHECKED_CAST")
    override fun <VM : androidx.lifecycle.ViewModel> create(modelClass: Class<VM>): VM = create() as VM
}
