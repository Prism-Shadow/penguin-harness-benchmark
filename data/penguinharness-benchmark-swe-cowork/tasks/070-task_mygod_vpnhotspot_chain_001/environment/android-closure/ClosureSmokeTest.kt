package be.mygod.vpnhotspot
import android.app.Application
import org.junit.Test
import org.junit.Assert.assertNotNull
import org.junit.runner.RunWith
import org.robolectric.RobolectricTestRunner
import org.robolectric.RuntimeEnvironment
import org.robolectric.annotation.Config
@RunWith(RobolectricTestRunner::class)
@Config(sdk = [30, 31], manifest = Config.NONE, application = Application::class)
class ClosureSmokeTest {
    @Test fun sdkStarts() { assertNotNull(RuntimeEnvironment.getApplication()) }
}
