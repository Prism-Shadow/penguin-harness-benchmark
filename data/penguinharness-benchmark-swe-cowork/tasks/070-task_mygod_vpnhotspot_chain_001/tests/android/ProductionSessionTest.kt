package be.mygod.vpnhotspot.root.daemon

import android.app.Application
import android.net.LocalServerSocket
import android.net.LocalSocket
import android.os.*
import android.system.Os
import android.system.ErrnoException
import android.system.OsConstants
import be.mygod.librootkotlinx.*
import be.mygod.vpnhotspot.App
import be.mygod.vpnhotspot.io.openReadChannel
import be.mygod.vpnhotspot.io.openWriteChannel
import be.mygod.vpnhotspot.net.Netd
import be.mygod.vpnhotspot.root.RootManager
import be.mygod.vpnhotspot.util.Services
import be.mygod.vpnhotspot.widget.SmartSnackbar
import dalvik.system.BaseDexClassLoader
import io.ktor.utils.io.*
import io.mockk.*
import kotlinx.coroutines.*
import kotlinx.coroutines.test.*
import org.junit.After
import org.junit.Assert.*
import org.junit.Test
import org.junit.runner.RunWith
import org.robolectric.annotation.Implementation
import org.robolectric.annotation.Implements
import org.robolectric.RobolectricTestRunner
import org.robolectric.annotation.Config
import org.robolectric.annotation.LooperMode
import java.io.FileDescriptor

/**
 * Robolectric's stock LocalServerSocket shadow still reaches the host-only
 * LocalSocketImpl.bind implementation.  The production controller only needs
 * the descriptor, accept and close boundary here, so provide those through a
 * scoped shadow while retaining the real controller/session code.
 */
@Implements(LocalServerSocket::class)
class ShadowProductionLocalServerSocket {
    companion object {
        private var descriptor: FileDescriptor? = null
        private var accepted: LocalSocket? = null

        fun install(fileDescriptor: FileDescriptor, socket: LocalSocket) {
            descriptor = fileDescriptor
            accepted = socket
        }

        fun reset() {
            descriptor = null
            accepted = null
        }
    }

    @Implementation
    fun __constructor__(name: String) = Unit

    @Implementation
    fun getFileDescriptor(): FileDescriptor = requireNotNull(descriptor)

    @Implementation
    fun accept(): LocalSocket = requireNotNull(accepted)

    @Implementation
    fun close() = Unit
}

/** Real public controller + generated Wire codec; substitutes only platform I/O. */
@OptIn(ExperimentalCoroutinesApi::class)
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [30, 31], manifest = Config.NONE, application = Application::class,
    shadows = [ShadowProductionLocalServerSocket::class])
@LooperMode(LooperMode.Mode.LEGACY)
class ProductionSessionTest {
    class PolicyService {
        val operations = java.util.concurrent.CopyOnWriteArrayList<List<Any>>()
        @Volatile var failOnce = false
        @Volatile var cancelOnce = false
        fun ipSecUpdateSecurityPolicy(uid: Int, family: Int, direction: Int,
            source: String, destination: String, spi: Int, mark: Int, mask: Int, ifId: Int) {
            if (cancelOnce) {
                cancelOnce = false
                throw java.util.concurrent.CancellationException("root cancelled")
            }
            if (failOnce) { failOnce = false; throw IllegalStateException("root rejected target") }
            operations.add(listOf(uid, family, direction, source, destination, spi, mark, mask, ifId))
        }
    }
    @After fun cleanup() { ShadowProductionLocalServerSocket.reset(); unmockkAll(); Dispatchers.resetMain() }

    private fun field(id: Int, value: Long): ByteArray {
        fun varint(number: Long): ByteArray {
            var n = number; val out = ArrayList<Byte>()
            while (n > 127) { out.add(((n and 127) or 128).toByte()); n = n ushr 7 }
            out.add(n.toByte()); return out.toByteArray()
        }
        return varint((id * 8).toLong()) + varint(value)
    }
    private fun field(id: Int, value: ByteArray) = field(id, value.size.toLong()).let {
        // id is below 16, so the tag has one byte.
        byteArrayOf((id * 8 + 2).toByte()) + it.drop(1).toByteArray() + value
    }
    private fun policy(id: Long, uid: Long, mark: Long): ByteArray {
        val request = field(1, uid) + field(2, "198.51.100.31".toByteArray()) +
            field(3, "192.0.2.31".toByteArray()) + field(4, mark) + field(5, 31L)
        return field(2, field(1, id) + field(4, request))
    }

    @Test fun sessionConsumesPolicyEventsAndContinuesAfterRootFailure() = runBlocking { exercise(false) }
    @Test fun cancellationPropagatesAndCloseCancelsTheCall() = runBlocking { exercise(true) }

    private suspend fun exercise(cancelAtEnd: Boolean) = coroutineScope {
        Dispatchers.setMain(Dispatchers.Unconfined)
        val incoming = ByteChannel(autoFlush = true)
        val outgoing = ByteChannel(autoFlush = true)
        val descriptor = FileDescriptor()
        val accepted = mockk<LocalSocket>(relaxed = true) { every { fileDescriptor } returns FileDescriptor() }
        ShadowProductionLocalServerSocket.install(descriptor, accepted)
        mockkStatic(Os::class)
        every { Os.fcntlInt(any(), any(), any()) } returns 0
        every { Os.read(any<FileDescriptor>(), any<ByteArray>(), any(), any()) } throws
            ErrnoException("read", OsConstants.EAGAIN)
        val looper = Looper.getMainLooper()
        // Keep Robolectric's real ShadowMessageQueue object. A bare MockK
        // MessageQueue is not backed by ShadowMessageQueue and crashes when
        // Handler recycles messages; spy the real queue so its shadow state
        // remains valid while allowing the descriptor callback to be driven.
        val queue = spyk(looper.queue)
        mockkObject(looper)
        every { looper.queue } returns queue
        every { queue.addOnFileDescriptorEventListener(any(), any(), any()) } answers {
            if (firstArg<FileDescriptor>() === descriptor)
                thirdArg<MessageQueue.OnFileDescriptorEventListener>().onFileDescriptorEvents(descriptor, 1)
        }
        mockkStatic(ParcelFileDescriptor::class)
        every { ParcelFileDescriptor.dup(any<FileDescriptor>()) } returns mockk(relaxed = true)
        mockkStatic("be.mygod.vpnhotspot.io.ParcelFileDescriptorReadChannelKt",
                    "be.mygod.vpnhotspot.io.ParcelFileDescriptorWriteChannelKt")
        every { any<ParcelFileDescriptor>().openReadChannel(any(), any()) } returns incoming
        every { any<ParcelFileDescriptor>().openWriteChannel(any(), any()) } returns outgoing
        val loader = mockk<BaseDexClassLoader> { every { findLibrary("vpnhotspotd") } returns "/fixture/vpnhotspotd" }
        mockkObject(App.Companion, RootManager, Netd, SmartSnackbar.Companion)
        every { App.app } returns mockk { every { classLoader } returns loader }
        every { SmartSnackbar.make(any<Throwable>()) } returns mockk(relaxed = true)
        val service = PolicyService()
        every { Netd.service } returns service
        every { Netd.ipSecUpdateSecurityPolicy } returns PolicyService::class.java.methods.single {
            it.name == "ipSecUpdateSecurityPolicy"
        }
        var cancelNextRoot = false
        val root = mockk<RootServer>()
        coEvery { root.execute(any<RootCommand<Parcelable?>>(), any()) } coAnswers {
            val command: Any = firstArg()
            if (command is RunDaemon) null
            else {
                if (cancelNextRoot) {
                    throw java.util.concurrent.CancellationException("root session cancelled")
                }
                @Suppress("UNCHECKED_CAST")
                (command as RootCommand<Parcelable?>).execute()
            }
        }
        coEvery { RootManager.acquire() } returns root
        coEvery { RootManager.release(root) } just Runs
        val start = async { DaemonController.startSession(SessionConfig(downstream = "wlan7")) }
        val request = withTimeout(5000) { ClientEnvelope.ADAPTER.decode(DaemonIpc.readFrame(outgoing)) }
        DaemonIpc.writeFrame(incoming, DaemonEnvelope(event = EventFrame(call_id = request.call_id, ack = Ack())).encode())
        val session = withTimeout(5000) { start.await() }
        val collected = async { session.closed.collect { error("policy event completed the session") } }
        try {
            DaemonIpc.writeFrame(incoming, policy(session.id, 10031, 61331))
            if (Build.VERSION.SDK_INT >= 31) withTimeout(5000) { while (service.operations.isEmpty()) yield() }
            else delay(100)
            assertTrue(collected.isActive)
            val expected = listOf(10031, OsConstants.AF_INET, 2, "198.51.100.31", "192.0.2.31", 0, 61331, -1, 31)
            assertEquals(if (Build.VERSION.SDK_INT >= 31) listOf(expected) else emptyList<List<Any>>(), service.operations)
            service.failOnce = true
            DaemonIpc.writeFrame(incoming, policy(session.id, 10032, 61332))
            DaemonIpc.writeFrame(incoming, policy(session.id, 10033, 61333))
            if (Build.VERSION.SDK_INT >= 31) withTimeout(5000) { while (service.operations.size < 2) yield() }
            else delay(100)
            assertTrue("Nonfatal failure terminated the event stream", collected.isActive)
            if (Build.VERSION.SDK_INT >= 31) {
                assertEquals(10033, service.operations.last()[0])
                verify(atLeast = 1) { SmartSnackbar.make(any<Throwable>()) }
            } else assertTrue(service.operations.isEmpty())
            if (cancelAtEnd && Build.VERSION.SDK_INT >= 31) {
                cancelNextRoot = true
                DaemonIpc.writeFrame(incoming, policy(session.id, 10034, 61334))
                try {
                    withTimeout(5000) { collected.await() }
                    fail("root cancellation was swallowed")
                } catch (expected: java.util.concurrent.CancellationException) {
                    assertFalse("cancellation timed out", expected is TimeoutCancellationException)
                }
                val cancellationFrame = async(Dispatchers.Unconfined, start = CoroutineStart.UNDISPATCHED) {
                    withTimeout(5000) { ClientEnvelope.ADAPTER.decode(DaemonIpc.readFrame(outgoing)) }
                }
                session.close()
                val cancel = cancellationFrame.await()
                assertEquals(session.id, cancel.call_id)
                assertNotNull(cancel.cancel)
            } else {
                DaemonIpc.writeFrame(incoming, DaemonEnvelope(complete = CompleteFrame(call_id = session.id)).encode())
                withTimeout(5000) { collected.await() }
            }
        } finally {
            collected.cancelAndJoin()
            session.close()
            start.cancelAndJoin()
        }
    }
}
