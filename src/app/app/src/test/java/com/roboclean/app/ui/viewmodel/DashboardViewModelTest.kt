package com.roboclean.app.ui.viewmodel

import com.roboclean.app.bluetooth.BluetoothService
import com.roboclean.app.bluetooth.RobotStatus
import io.mockk.*
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.test.*
import org.junit.After
import org.junit.Assert.*
import org.junit.Before
import org.junit.Test

@OptIn(ExperimentalCoroutinesApi::class)
class DashboardViewModelTest {

    private lateinit var btService: BluetoothService
    private lateinit var connectedFlow: MutableStateFlow<Boolean>
    private lateinit var statusFlow: MutableStateFlow<RobotStatus>
    private val testDispatcher = StandardTestDispatcher()

    @Before
    fun setUp() {
        Dispatchers.setMain(testDispatcher)
        btService = mockk(relaxed = true)
        connectedFlow = MutableStateFlow(false)
        statusFlow = MutableStateFlow(RobotStatus(0, 0f, 0f, false, 0))
        every { btService.isConnected } returns connectedFlow
        every { btService.robotStatus } returns statusFlow
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun `isConnected reflects BluetoothService state`() = runTest {
        connectedFlow.value = true
        val vm = DashboardViewModel(btService)
        testDispatcher.scheduler.advanceUntilIdle()
        assertEquals(true, vm.isConnected.value)
    }

    @Test
    fun `robotStatus reflects BluetoothService state`() = runTest {
        statusFlow.value = RobotStatus(75, 50f, 5.5f, true, 30)
        val vm = DashboardViewModel(btService)
        testDispatcher.scheduler.advanceUntilIdle()
        assertEquals(75, vm.robotStatus.value.batteryPercent)
        assertEquals(50f, vm.robotStatus.value.batteryVoltage)
        assertEquals(5.5f, vm.robotStatus.value.totalKm)
        assertTrue(vm.robotStatus.value.isWorking)
    }

    @Test
    fun `estimated hours with full battery`() = runTest {
        statusFlow.value = RobotStatus(100, 54f, 0f, false, 25)
        val vm = DashboardViewModel(btService)
        testDispatcher.scheduler.advanceUntilIdle()
        assertTrue(vm.estimatedHours().contains("4"))
    }

    @Test
    fun `estimated hours with half battery`() = runTest {
        statusFlow.value = RobotStatus(50, 48f, 0f, false, 25)
        val vm = DashboardViewModel(btService)
        testDispatcher.scheduler.advanceUntilIdle()
        assertTrue(vm.estimatedHours().contains("2"))
    }

    @Test
    fun `estimated hours with empty battery`() = runTest {
        statusFlow.value = RobotStatus(0, 42f, 0f, false, 25)
        val vm = DashboardViewModel(btService)
        testDispatcher.scheduler.advanceUntilIdle()
        assertTrue(vm.estimatedHours().contains("0"))
    }

    @Test
    fun `emergencyStop calls BluetoothService`() = runTest {
        val vm = DashboardViewModel(btService)
        vm.emergencyStop()
        verify(exactly = 1) { btService.emergencyStop() }
    }

    @Test
    fun `returnToCharge sends route command`() = runTest {
        val vm = DashboardViewModel(btService)
        vm.returnToCharge()
        verify(exactly = 1) { btService.setRoute(match { it.contains("return_to_charge") }) }
    }

    @Test
    fun `toggleStartStop queries status`() = runTest {
        val vm = DashboardViewModel(btService)
        vm.toggleStartStop()
        verify(exactly = 1) { btService.queryStatus() }
    }
}
