package com.roboclean.app.ui.viewmodel

import com.roboclean.app.bluetooth.BluetoothService
import com.roboclean.app.data.PersistentWaypoint
import com.roboclean.app.data.RouteRepository
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
class RouteViewModelTest {

    private lateinit var repository: RouteRepository
    private lateinit var btService: BluetoothService
    private lateinit var waypointsFlow: MutableStateFlow<List<PersistentWaypoint>>
    private val testDispatcher = StandardTestDispatcher()

    @Before
    fun setUp() {
        Dispatchers.setMain(testDispatcher)
        repository = mockk(relaxed = true)
        btService = mockk(relaxed = true)
        waypointsFlow = MutableStateFlow(emptyList())
        every { repository.waypointsFlow } returns waypointsFlow
        // Mock save 真正更新 backing flow → ViewModel 的 stateIn 就能读到新值
        coEvery { repository.save(any()) } answers {
            waypointsFlow.value = arg(0)
        }
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun `initial waypoints loaded from repository`() = runTest {
        val persisted = listOf(PersistentWaypoint(1, "起点"), PersistentWaypoint(2, "终点"))
        waypointsFlow.value = persisted
        val vm = RouteViewModel(repository, btService)
        testDispatcher.scheduler.advanceUntilIdle()
        assertEquals(persisted, vm.waypoints.value)
    }

    @Test
    fun `addWaypoint adds to list`() = runTest {
        waypointsFlow.value = listOf(PersistentWaypoint(1, "A"))
        val vm = RouteViewModel(repository, btService)
        testDispatcher.scheduler.advanceUntilIdle()

        vm.addWaypoint("B")
        testDispatcher.scheduler.advanceUntilIdle()

        assertEquals(2, vm.waypoints.value.size)
        assertEquals("A", vm.waypoints.value[0].name)
        assertEquals("B", vm.waypoints.value[1].name)
    }

    @Test
    fun `deleteWaypoint removes from list`() = runTest {
        waypointsFlow.value = listOf(
            PersistentWaypoint(1, "A"), PersistentWaypoint(2, "B"), PersistentWaypoint(3, "C")
        )
        val vm = RouteViewModel(repository, btService)
        testDispatcher.scheduler.advanceUntilIdle()

        vm.deleteWaypoint(2)
        testDispatcher.scheduler.advanceUntilIdle()

        assertEquals(2, vm.waypoints.value.size)
        assertEquals(listOf(1, 3), vm.waypoints.value.map { it.id })
    }

    @Test
    fun `deleteWaypoint with non-existent id does nothing`() = runTest {
        waypointsFlow.value = listOf(PersistentWaypoint(1, "A"))
        val vm = RouteViewModel(repository, btService)
        testDispatcher.scheduler.advanceUntilIdle()

        vm.deleteWaypoint(999)
        testDispatcher.scheduler.advanceUntilIdle()

        assertEquals(1, vm.waypoints.value.size)
    }

    @Test
    fun `addWaypoint to empty list starts from id 1`() = runTest {
        val vm = RouteViewModel(repository, btService)
        testDispatcher.scheduler.advanceUntilIdle()

        vm.addWaypoint("first")
        testDispatcher.scheduler.advanceUntilIdle()

        assertEquals(1, vm.waypoints.value.size)
        assertEquals(1, vm.waypoints.value[0].id)
    }

    @Test
    fun `save delegates to repository`() = runTest {
        val vm = RouteViewModel(repository, btService)
        testDispatcher.scheduler.advanceUntilIdle()
        val waypoints = listOf(PersistentWaypoint(1, "test"))
        vm.save(waypoints)
        testDispatcher.scheduler.advanceUntilIdle()
        coVerify(exactly = 1) { repository.save(waypoints) }
    }

    @Test
    fun `sendToRobot calls BluetoothService`() = runTest {
        waypointsFlow.value = listOf(PersistentWaypoint(1, "test"))
        val vm = RouteViewModel(repository, btService)
        testDispatcher.scheduler.advanceUntilIdle()

        vm.sendToRobot()
        testDispatcher.scheduler.advanceUntilIdle()

        verify(exactly = 1) { btService.setRoute(any()) }
    }

    @Test
    fun `clearUiState resets to Idle`() = runTest {
        val vm = RouteViewModel(repository, btService)
        testDispatcher.scheduler.advanceUntilIdle()
        vm.clearUiState()
        assertEquals(RouteViewModel.UiState.Idle, vm.uiState.value)
    }
}
