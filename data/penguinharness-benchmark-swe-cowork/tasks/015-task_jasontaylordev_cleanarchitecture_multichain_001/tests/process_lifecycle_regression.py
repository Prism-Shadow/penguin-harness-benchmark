"""Exercise real child processes; no process from another run is selected."""
import os
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).parent/'private-runtime/task-environment'))
from process_support import stop_process_group


class ProcessLifecycleRegression(unittest.TestCase):
    def exercise(self, parent_exits):
        with tempfile.TemporaryDirectory(prefix='owned-processes-') as directory:
            d=Path(directory)
            child = 'from pathlib import Path; import time,signal; signal.signal(signal.SIGTERM,signal.SIG_IGN); Path('+repr(str(d/'ready'))+').touch(); time.sleep(.8); Path('+repr(str(d/'late-child'))+').touch(); time.sleep(20)'
            parent = 'import subprocess,sys,time; subprocess.Popen([sys.executable,"-c",'+repr(child)+']); '+('time.sleep(.05)' if parent_exits else 'time.sleep(20)')
            unrelated = subprocess.Popen([sys.executable,'-c','import time; time.sleep(20)'],start_new_session=True)
            proc = subprocess.Popen([sys.executable,'-c',parent],start_new_session=True)
            try:
                deadline=time.monotonic()+5
                while not (d/'ready').exists():
                    self.assertLess(time.monotonic(),deadline,'child did not initialize')
                    time.sleep(.01)
                if parent_exits:
                    proc.wait(timeout=5)
                stop_process_group(proc,timeout=.2)
                self.assertIsNotNone(proc.returncode)
                self.assertIsNone(unrelated.poll(),'cleanup selected an unrelated session')
                time.sleep(1)
                self.assertFalse((d/'late-child').exists(),'child survived launcher cleanup')
            finally:
                stop_process_group(proc,timeout=.2)
                stop_process_group(unrelated,timeout=.2)

    def test_cleanup_stops_live_launcher_and_stubborn_child(self):
        self.exercise(False)

    def test_cleanup_stops_child_even_after_launcher_exits(self):
        self.exercise(True)


if __name__=='__main__':
    unittest.main()
