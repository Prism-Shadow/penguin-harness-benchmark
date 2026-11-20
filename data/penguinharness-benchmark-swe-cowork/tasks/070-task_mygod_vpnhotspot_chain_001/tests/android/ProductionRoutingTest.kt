package be.mygod.vpnhotspot.root.daemon

import android.app.Application
import android.net.LinkProperties
import android.net.Network
import be.mygod.vpnhotspot.net.Routing
import be.mygod.vpnhotspot.net.NetlinkNeighbour
import be.mygod.vpnhotspot.net.monitor.Upstream
import be.mygod.vpnhotspot.net.monitor.Upstreams
import be.mygod.vpnhotspot.room.AppDatabase
import io.mockk.*
import kotlinx.coroutines.*
import kotlinx.coroutines.channels.Channel
import kotlinx.coroutines.flow.*
import kotlinx.collections.immutable.ImmutableCollection
import kotlinx.collections.immutable.persistentListOf
import org.junit.After
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import java.net.InetAddress

/** Exercises Routing.start and the public daemon boundary, not its private trackers. */
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [31], manifest = Config.NONE, application = Application::class)
class ProductionRoutingTest {
    @After fun cleanup() = unmockkAll()

    @Test fun snapshotsReachSessionWithMonotonicGeneration() = runBlocking {
        val primary = MutableStateFlow<Upstream?>(null)
        val fallback = MutableStateFlow<Upstream?>(null)
        mockkObject(Upstreams, NetlinkNeighbour.Companion, AppDatabase.Companion, DaemonController)
        every { Upstreams.primary } returns primary
        every { Upstreams.fallback } returns fallback
        // Keep the public SharedFlow shape while supplying an immutable empty
        // snapshot for this upstream-only scenario.
        val neighbours = MutableSharedFlow<ImmutableCollection<NetlinkNeighbour>>(replay = 1).apply {
            tryEmit(persistentListOf<NetlinkNeighbour>())
        }
        every { NetlinkNeighbour.snapshots } returns neighbours.asSharedFlow()
        every { AppDatabase.instance } returns mockk {
            every { clientRecordDao.observeBlockedMacs() } returns flowOf(emptyList())
        }
        val configs = Channel<SessionConfig>(Channel.UNLIMITED)
        val session = mockk<DaemonController.SessionCall> {
            every { id } returns 730
            every { closed } returns flow { awaitCancellation() }
            coEvery { close() } just Runs
        }
        coEvery { DaemonController.startSession(any()) } coAnswers {
            configs.send(firstArg()); session
        }
        coEvery { DaemonController.replaceSession(730, any()) } coAnswers {
            configs.send(secondArg()); Unit
        }
        val routing = Routing(this, "wlan7")
        try {
            assertTrue(routing.start())
            assertFalse(routing.start())
            val initial = withTimeout(5000) { configs.receive() }
            // StateFlow legitimately emits its initial null snapshot. It equals
            // the session's initial empty state and must not create a replacement.
            // Unlike assigning an equal StateFlow value later, this emission
            // actually reaches Routing's collector.
            assertNull("Identical initial upstream snapshots replaced the session",
                withTimeoutOrNull(300) { configs.receive() })
            fun generation(value: SessionConfig): Long {
                // Read the public wire representation, including a baseline
                // that does not yet know field 12. No private layout is assumed.
                val bytes = SessionConfig.ADAPTER.encode(value)
                var pos = 0
                fun number(): Long {
                    var result = 0L; var shift = 0
                    do { val v = bytes[pos++].toInt() and 255
                        result = result or ((v and 127).toLong() shl shift); shift += 7
                        if (v and 128 == 0) return result
                    } while (shift < 70)
                    error("invalid varint")
                }
                while (pos < bytes.size) {
                    val key = number().toInt()
                    when (key and 7) {
                        0 -> { val v = number(); if (key ushr 3 == 12) return v }
                        1 -> pos += 8
                        2 -> { val size = number().toInt(); pos += size }
                        5 -> pos += 4
                        else -> error("invalid wire type")
                    }
                }
                return 0
            }
            fun network(handle: Long) = mockk<Network>(relaxed = true).also {
                every { it.networkHandle } returns handle
            }
            fun props(iface: String, mtu: Int) = LinkProperties().apply {
                interfaceName = iface
                this.mtu = mtu
            }
            val network31 = network(31)
            val network43 = network(43)
            val firstProps = props("ipsec31", 1500)
            primary.value = Upstream(network31, firstProps)
            val first = withTimeout(5000) { configs.receive() }
            assertEquals(listOf("ipsec31"), first.primary_upstream_interfaces)
            assertTrue(generation(first) > generation(initial))
            // A changed public LinkProperties snapshot preserves the interface
            // while still forcing a new generation. The test does not depend on
            // hidden Android constructors or DNS mutators.
            val changed = props("ipsec31", 1501)
            primary.value = Upstream(network31, changed)
            val second = withTimeout(5000) { configs.receive() }
            assertEquals(first.primary_upstream_interfaces, second.primary_upstream_interfaces)
            assertTrue(generation(second) > generation(first))
            primary.value = Upstream(network31, changed)
            assertNull(withTimeoutOrNull(250) { configs.receive() })
            fallback.value = Upstream(network43, props("ipsec43", 1500))
            val third = withTimeout(5000) { configs.receive() }
            assertEquals(listOf("ipsec43"), third.fallback_upstream_interfaces)
            assertTrue(generation(third) > generation(second))
            primary.value = null
            val removed = withTimeout(5000) { configs.receive() }
            assertTrue(removed.primary_upstream_interfaces.isEmpty())
            assertTrue(generation(removed) > generation(third))
        } finally { routing.revert() }
        coVerify(exactly = 1) { session.close() }
    }
}
