#!/usr/bin/env python3
"""Local smart-HTTP fixture using the installed native git http-backend.
Usage: offline-git-http.py <directory containing bare repositories> [port]
Serves loopback only. Each repository is a real Git repository, not canned HTTP.
"""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import os,subprocess,sys
from urllib.parse import urlsplit
root=Path(sys.argv[1]).resolve();port=int(sys.argv[2]) if len(sys.argv)>2 else 9999
class Handler(BaseHTTPRequestHandler):
 def handle_git(self):
  url=urlsplit(self.path);path=url.path
  # Accept the local CORS proxy prefix used by the repository's Node tests.
  marker=path.find('/repo.git/')
  if marker<0:self.send_error(404);return
  path=path[marker:]
  if '..' in path.split('/'):self.send_error(400);return
  size=int(self.headers.get('Content-Length','0'));body=self.rfile.read(size)
  env=dict(os.environ,GIT_PROJECT_ROOT=str(root),GIT_HTTP_EXPORT_ALL='1',PATH_INFO=path,
   QUERY_STRING=url.query,REQUEST_METHOD=self.command,CONTENT_TYPE=self.headers.get('Content-Type',''),
   CONTENT_LENGTH=str(size),REMOTE_ADDR='127.0.0.1',SERVER_PROTOCOL='HTTP/1.1')
  out=subprocess.run(['git','http-backend'],input=body,capture_output=True,env=env,timeout=30)
  if out.returncode:self.send_error(500);return
  headers,_,payload=out.stdout.partition(b'\r\n\r\n');lines=headers.decode().split('\r\n');status=200
  for line in lines:
   if line.lower().startswith('status:'):status=int(line.split()[1])
  self.send_response(status)
  for line in lines:
   if ':' in line:
    key,value=line.split(':',1)
    if key.lower()!='status':self.send_header(key,value.strip())
  self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
 do_GET=handle_git
 do_POST=handle_git
ThreadingHTTPServer(('127.0.0.1',port),Handler).serve_forever()
