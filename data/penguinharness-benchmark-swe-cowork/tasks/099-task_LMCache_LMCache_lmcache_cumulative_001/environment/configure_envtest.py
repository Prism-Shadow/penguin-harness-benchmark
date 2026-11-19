"""Keep complete native envtest binaries; configure offline listener defaults."""
import pathlib,shutil,hashlib
assets=pathlib.Path('/opt/envtest-path').read_text().strip()
root=pathlib.Path(assets)
server=root/'kube-apiserver';real=root/'kube-apiserver.real'
assert server.is_file() and (root/'etcd').is_file(), assets
if not real.exists():server.rename(real)
shutil.copyfile('/opt/task-tools/kube-apiserver-offline.py',server)
server.chmod(0o755)
print('ENVTEST_NATIVE_SERVER',assets,hashlib.sha256(real.read_bytes()).hexdigest(),flush=True)
