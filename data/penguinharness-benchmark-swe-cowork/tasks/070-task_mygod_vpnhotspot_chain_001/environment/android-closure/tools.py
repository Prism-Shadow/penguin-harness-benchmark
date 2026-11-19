import urllib.request, pathlib, hashlib, zipfile
from datetime import datetime, timezone
print('TOOLS START UTC',datetime.now(timezone.utc).isoformat(),flush=True)
root=pathlib.Path('/opt/android-closure'); root.mkdir(parents=True,exist_ok=True)
url='https://services.gradle.org/distributions/gradle-9.5.0-bin.zip'
print('Acquiring',url,flush=True)
expected='553c78f50dafcd54d65b9a444649057857469edf836431389695608536d6b746'
with urllib.request.urlopen(url+'.sha256',timeout=45) as f: assert f.read().decode().split()[0] == expected
with urllib.request.urlopen(url,timeout=90) as f: data=f.read()
assert hashlib.sha256(data).hexdigest()==expected
archive=root/'gradle.zip'; archive.write_bytes(data)
with zipfile.ZipFile(archive) as f: f.extractall(root/'gradle')
archive.unlink()
(root/'gradle/gradle-9.5.0/bin/gradle').chmod(0o755)
print('Gradle distribution sha256',expected,flush=True)
import os, subprocess, json, shutil
# Seed the repository's actual Gradle Wrapper cache as well as the `gradle`
# command. --offline is a Gradle flag, so the wrapper itself otherwise attempts
# to download its distribution before Gradle can honor that flag.
number=int.from_bytes(hashlib.md5(url.encode()).digest(),'big')
digits='0123456789abcdefghijklmnopqrstuvwxyz';distribution_hash=''
while number:
 number,digit=divmod(number,36);distribution_hash=digits[digit]+distribution_hash
wrapper=root/'gradle-home/wrapper/dists/gradle-9.5.0-bin'/distribution_hash
wrapper.mkdir(parents=True)
distribution=root/'gradle/gradle-9.5.0'
shutil.move(str(distribution),wrapper/distribution.name)
distribution.symlink_to(os.path.relpath(wrapper/distribution.name,distribution.parent),target_is_directory=True)
(wrapper/'gradle-9.5.0-bin.zip.ok').touch()
subprocess.run(['/app/code/gradlew','--offline','--version'],cwd='/app/code',
               env=dict(os.environ,GRADLE_USER_HOME=str(root/'gradle-home')),check=True)
print('Pinned offline Gradle wrapper distribution',distribution_hash,flush=True)
sdk=root/'sdk'; sdk.mkdir(exist_ok=True)
url='https://dl.google.com/android/repository/commandlinetools-linux-13114758_latest.zip'
print('Acquiring',url,flush=True)
with urllib.request.urlopen(url,timeout=120) as f: data=f.read()
assert hashlib.sha256(data).hexdigest() == '7ec965280a073311c339e571cd5de778b9975026cfcbe79f2b1cdcb1e15317ee'
print('Command-line tools sha256',hashlib.sha256(data).hexdigest(),flush=True)
archive=root/'commandline.zip'; archive.write_bytes(data)
with zipfile.ZipFile(archive) as f: f.extractall(sdk/'cmdline-tools')
(sdk/'cmdline-tools/cmdline-tools').rename(sdk/'cmdline-tools/latest');archive.unlink()
for p in (sdk/'cmdline-tools/latest/bin').iterdir():p.chmod(0o755)
env=dict(os.environ,ANDROID_HOME=str(sdk),ANDROID_SDK_ROOT=str(sdk),GRADLE_USER_HOME=str(root/'gradle-home'))
manager=str(sdk/'cmdline-tools/latest/bin/sdkmanager')
subprocess.run([manager,'--licenses'],input='y\n'*100,text=True,env=env,check=True,stdout=subprocess.DEVNULL)
subprocess.run([manager,'platforms;android-36.1','build-tools;36.0.0','ndk;29.0.14206865'],env=env,check=True)
subprocess.run(['rustup','target','add','--toolchain','1.89.0','aarch64-linux-android','armv7-linux-androideabi','i686-linux-android','x86_64-linux-android'],check=True)
subprocess.run(['cargo','install','--locked','cargo-ndk','--version','4.1.0'], env=dict(os.environ, CARGO_NET_OFFLINE='false'), check=True)
for p in pathlib.Path('/opt/cargo').glob('registry/src/*/protoc-bin-vendored-linux-*/bin/protoc'): p.chmod(0o755)
env['CARGO_NET_OFFLINE']='false'
env['PATH']='/opt/cargo/bin:'+env.get('PATH','')
for variable in ('CARGO_TARGET_DIR','RUSTFLAGS','RUSTDOCFLAGS','LD_PRELOAD','LD_LIBRARY_PATH'):
 env.pop(variable,None)
env['ANDROID_NDK_HOME']=str(sdk/'ndk/29.0.14206865')

print('Pinned Android/Rust toolchains installed',flush=True)
print('TOOLS FINISHED UTC',datetime.now(timezone.utc).isoformat(),flush=True)
