package be.mygod.vpnhotspot.root.daemon

import io.ktor.utils.io.ByteReadChannel
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test
import java.io.File
import java.nio.ByteBuffer

class ProductionWireTest {
    @Test
    fun readsActualRustCounterReplies() = runBlocking {
        val capture = File(requireNotNull(System.getenv("VPNHOTSPOT_IPC_CAPTURE")))
        val records = capture.readLines().filter { it.isNotEmpty() }
        assertTrue("No actual daemon captures", records.size >= 4)
        for (record in records) {
            val columns = record.split('\t')
            assertEquals(3, columns.size)
            val packet = columns[1].chunked(2).map { it.toInt(16).toByte() }.toByteArray()
            val framed = ByteBuffer.allocate(4 + packet.size).putInt(packet.size).put(packet).array()
            val reply = DaemonEnvelope.ADAPTER.decode(DaemonIpc.readFrame(ByteReadChannel(framed))).reply
            assertNotNull(reply)
            assertEquals(columns[0].toLong(), reply!!.call_id)
            assertNotNull(reply.traffic_counter_lines)
            val expected = if (columns[2].isEmpty()) emptyList() else columns[2].split(',').map { encoded ->
                encoded.chunked(2).map { it.toInt(16).toByte() }.toByteArray().toString(Charsets.UTF_8)
            }
            assertEquals(expected, reply.traffic_counter_lines!!.lines)
        }
    }
}
