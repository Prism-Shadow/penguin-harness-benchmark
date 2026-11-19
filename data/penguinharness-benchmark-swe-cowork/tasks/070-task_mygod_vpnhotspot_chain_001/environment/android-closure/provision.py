"""Run Python provisioning stages after the Dockerfile's resources are staged.

The Dockerfile owns native library compilation, /opt resource copies, public
document installation and runtime ENV. Build it for a complete environment.
"""
import pathlib,subprocess,sys
for name in ('tools.py','buildcache.py','finalize.py'):
 if name == 'finalize.py':
  subprocess.run(['rustup','component','add','--toolchain','1.89.0','rustfmt','clippy'],check=True)
 subprocess.run([sys.executable,str(pathlib.Path(__file__).with_name(name))],check=True)
