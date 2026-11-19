import os,subprocess,time,pathlib,json
root=pathlib.Path('/app/code');out=pathlib.Path('/logs/host-diagnostic');out.mkdir(parents=True,exist_ok=True)
print('BUILD',flush=True)
subprocess.run(['dotnet','build','src/AppHost/AppHost.csproj','--no-restore','-m:2'],cwd=root,check=True)
with (out/'host.log').open('w') as log:
 env=dict(os.environ,Logging__LogLevel__Default='Debug')
 p=subprocess.Popen(['dotnet','run','--project','src/AppHost/AppHost.csproj','--no-restore','--no-build','--launch-profile','http'],cwd=root,env=env,stdout=log,stderr=subprocess.STDOUT)
 try:
  for _ in range(90):
   if p.poll() is not None:break
   time.sleep(1)
 finally:
  p.terminate()
  try:p.wait(timeout=20)
  except subprocess.TimeoutExpired:p.kill();p.wait()
print('HOST LOG',flush=True);print((out/'host.log').read_text()[-45000:])
for path in pathlib.Path('/tmp').glob('**/*'):
 if path.is_file() and path.suffix=='.log' and path.stat().st_size<2000000:
  try:text=path.read_text()
  except (UnicodeError,OSError):continue
  if 'webfrontend' in text or 'ERR!' in text or 'npm error' in text: print('LOG',str(path),text[-20000:])
for path in pathlib.Path('/opt/nuget/packages/aspire.hosting/13.1.2').glob('lib/*/*.xml'):
 text=path.read_text();lines=text.splitlines()
 for i,line in enumerate(lines):
  if 'ResourceLoggerService.WatchAsync' in line or 'ResourceLoggerService.Get' in line:print('\n'.join(lines[i:i+18]))
