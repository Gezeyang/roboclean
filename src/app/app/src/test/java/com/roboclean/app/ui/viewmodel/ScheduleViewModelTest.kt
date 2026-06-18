package com.roboclean.app.ui.viewmodel

import com.roboclean.app.bluetooth.BluetoothService
import com.roboclean.app.data.PersistentTimeSlot
import com.roboclean.app.data.ScheduleRepository
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
class ScheduleViewModelTest {

    private lateinit var repository: ScheduleRepository
    private lateinit var btService: BluetoothService
    private lateinit var slotsFlow: MutableStateFlow<List<PersistentTimeSlot>>
    private val testDispatcher = StandardTestDispatcher()

    @Before
    fun setUp() {
        Dispatchers.setMain(testDispatcher)
        repository = mockk(relaxed = true)
        btService = mockk(relaxed = true)
        slotsFlow = MutableStateFlow(emptyList())
        every { repository.slotsFlow } returns slotsFlow
        coEvery { repository.save(any()) } answers {
            slotsFlow.value = arg(0)
        }
    }

    @After
    fun tearDown() {
        Dispatchers.resetMain()
    }

    @Test
    fun `addTimeSlot adds valid slot`() = runTest {
        val vm = ScheduleViewModel(repository, btService)
        testDispatcher.scheduler.advanceUntilIdle()

        vm.addTimeSlot("周一", 8, 0, 9, 30)
        testDispatcher.scheduler.advanceUntilIdle()

        assertEquals(1, vm.timeSlots.value.size)
        val slot = vm.timeSlots.value[0]
        assertEquals("周一", slot.dayOfWeek)
        assertEquals(8, slot.startHour)
        assertEquals(0, slot.startMinute)
        assertEquals(9, slot.endHour)
        assertEquals(30, slot.endMinute)
        assertTrue(slot.enabled)
    }

    @Test
    fun `addTimeSlot clamps invalid values`() = runTest {
        val vm = ScheduleViewModel(repository, btService)
        testDispatcher.scheduler.advanceUntilIdle()

        vm.addTimeSlot("周二", 25, 70, 26, 80)
        testDispatcher.scheduler.advanceUntilIdle()

        val slot = vm.timeSlots.value[0]
        assertEquals(23, slot.startHour)
        assertEquals(59, slot.startMinute)
    }

    @Test
    fun `deleteSlot removes correct item`() = runTest {
        slotsFlow.value = listOf(
            PersistentTimeSlot(1, "周一", 8, 0, 9, 0),
            PersistentTimeSlot(2, "周一", 10, 0, 11, 0),
            PersistentTimeSlot(3, "周二", 14, 0, 15, 0)
        )
        val vm = ScheduleViewModel(repository, btService)
        testDispatcher.scheduler.advanceUntilIdle()

        vm.deleteSlot(2)
        testDispatcher.scheduler.advanceUntilIdle()

        assertEquals(2, vm.timeSlots.value.size)
        assertEquals(listOf(1, 3), vm.timeSlots.value.map { it.id })
    }

    @Test
    fun `toggleSlot flips enabled state`() = runTest {
        slotsFlow.value = listOf(PersistentTimeSlot(1, "周一", 8, 0, 9, 0, true))
        val vm = ScheduleViewModel(repository, btService)
        testDispatcher.scheduler.advanceUntilIdle()

        vm.toggleSlot(1)
        testDispatcher.scheduler.advanceUntilIdle()
        assertFalse(vm.timeSlots.value[0].enabled)

        vm.toggleSlot(1)
        testDispatcher.scheduler.advanceUntilIdle()
        assertTrue(vm.timeSlots.value[0].enabled)
    }

    @Test
    fun `toggleSlot on non-existent id does nothing`() = runTest {
        slotsFlow.value = listOf(PersistentTimeSlot(1, "周一", 8, 0, 9, 0, true))
        val vm = ScheduleViewModel(repository, btService)
        testDispatcher.scheduler.advanceUntilIdle()

        vm.toggleSlot(999)
        testDispatcher.scheduler.advanceUntilIdle()

        assertEquals(1, vm.timeSlots.value.size)
        assertTrue(vm.timeSlots.value[0].enabled)
    }

    @Test
    fun `groupedByDay groups slots correctly`() = runTest {
        slotsFlow.value = listOf(
            PersistentTimeSlot(1, "周一", 8, 0, 9, 0),
            PersistentTimeSlot(2, "周一", 10, 0, 11, 0),
            PersistentTimeSlot(3, "周三", 14, 0, 15, 0)
        )
        val vm = ScheduleViewModel(repository, btService)
        testDispatcher.scheduler.advanceUntilIdle()

        val grouped = vm.groupedByDay.value
        assertEquals(2, grouped.size)
        assertEquals(2, grouped["周一"]?.size)
        assertEquals(1, grouped["周三"]?.size)
    }

    @Test
    fun `sendToRobot calls BluetoothService`() = runTest {
        slotsFlow.value = listOf(PersistentTimeSlot(1, "周一", 8, 0, 9, 0))
        val vm = ScheduleViewModel(repository, btService)
        testDispatcher.scheduler.advanceUntilIdle()

        vm.sendToRobot()
        testDispatcher.scheduler.advanceUntilIdle()

        verify(exactly = 1) { btService.setSchedule(any()) }
    }

    @Test
    fun `save delegates to repository`() = runTest {
        val vm = ScheduleViewModel(repository, btService)
        testDispatcher.scheduler.advanceUntilIdle()
        val slots = listOf(PersistentTimeSlot(1, "周五", 9, 0, 17, 0))
        vm.save(slots)
        testDispatcher.scheduler.advanceUntilIdle()
        coVerify(exactly = 1) { repository.save(slots) }
    }
}
