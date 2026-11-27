"""Exercise the actual Node supervisor and shared countdown without a model or GPU."""
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import unittest

TOOLS = Path(__file__).resolve().parents[1]
ROOT = TOOLS.parents[1]
sys.path.insert(0, str(TOOLS))
from timer import remaining_seconds
SUPERVISOR = ROOT / 'agents/penguin_agent/deadline.mjs'


class TimerTests(unittest.TestCase):
    def test_countdown_reads_absolute_deadline_not_healthcheck_start(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)/'deadline.json';p.write_text(json.dumps({'deadline_ms':5000}))
            self.assertEqual(remaining_seconds(p,1000),4)
            self.assertEqual(remaining_seconds(p,4999),1)
            self.assertEqual(remaining_seconds(p,5000),0)
            self.assertEqual(remaining_seconds(p,9000),0)
            p.write_text('{"deadline_ms":true}')
            with self.assertRaises(ValueError): remaining_seconds(p,0)

    @unittest.skipUnless(shutil.which('node'), 'Node required for real supervisor tests')
    def test_same_deadline_stops_process_even_with_old_timer_state(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);deadline=root/'deadline.json';receipt=root/'receipt.json';signal=root/'signal.json'
            deadline.write_text('{"deadline_ms":1}')  # old boot/installation state is ignored
            child=root/'child.cjs'
            child.write_text('''const fs=require('fs');
process.on('SIGINT',()=>{fs.writeFileSync(process.argv[2],JSON.stringify({at:Date.now(),state:JSON.parse(fs.readFileSync(process.argv[3]))}));process.exit(0);});
setInterval(()=>{},50);
''')
            start=time.time()*1000
            r=subprocess.run([shutil.which('node'),str(SUPERVISOR),str(deadline),str(receipt),'1','2',
                              shutil.which('node'),str(child),str(signal),str(deadline)],capture_output=True,timeout=8)
            self.assertEqual(r.returncode,0,r.stderr)
            state=json.loads(deadline.read_text());result=json.loads(receipt.read_text());seen=json.loads(signal.read_text())
            self.assertGreaterEqual(state['started_at_ms'],start-5)
            self.assertEqual(state['deadline_ms']-state['started_at_ms'],1000)
            self.assertEqual(result['deadline_ms'],state['deadline_ms'])
            self.assertEqual(seen['state']['deadline_ms'],state['deadline_ms'])
            self.assertGreaterEqual(seen['at'],state['deadline_ms']-10)
            self.assertLess(seen['at']-state['deadline_ms'],1000)
            self.assertTrue(result['timed_out'])
            self.assertEqual(remaining_seconds(deadline,seen['at']),0)

    @unittest.skipUnless(shutil.which('node'), 'Node required for real supervisor tests')
    def test_early_exit_preserves_failure_and_does_not_report_timeout(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d)
            r=subprocess.run([shutil.which('node'),str(SUPERVISOR),str(p/'deadline'),str(p/'receipt'),'5','1',
                              shutil.which('node'),'-e','process.exit(7)'],capture_output=True,timeout=5)
            self.assertEqual(r.returncode,7)
            self.assertFalse(json.loads((p/'receipt').read_text())['timed_out'])

    @unittest.skipUnless(shutil.which('node'), 'Node required for actual run.sh test')
    def test_actual_run_shell_supervises_and_records_timeout(self):
        with tempfile.TemporaryDirectory() as d:
            p=Path(d);prefix=p/'prefix';logs=p/'logs';home=p/'home';workspace=p/'workspace'
            (prefix/'node/bin').mkdir(parents=True);(prefix/'bin').mkdir();workspace.mkdir()
            (prefix/'node/bin/node').symlink_to(shutil.which('node'))
            shutil.copy2(SUPERVISOR,prefix/'deadline.mjs')
            (prefix/'instruction.md').write_text('fixture')
            (prefix/'helper.mjs').write_text('''import fs from 'node:fs';
const [cmd,...a]=process.argv.slice(2);
if(cmd==='now') console.log(Date.now());
else if(cmd==='run-status') {let r=JSON.parse(fs.readFileSync(a[0]));console.log(r.status+' '+r.sessionId);}
else if(cmd==='outcome') fs.writeFileSync(a[0],a[1]);
else console.log('{}');
''')
            cli=prefix/'bin/penguin'
            cli.write_text('''#!/usr/bin/env node
const fs=require('fs');const args=process.argv.slice(2);const pid=process.env.PENGUIN_HOME+'.pid';
if(args[0]==='server' && args[1]==='status') console.log('{"running":true}');
else if(args[0]==='server' && args[1]==='stop') {try{process.kill(Number(fs.readFileSync(pid)),'SIGTERM');}catch{} console.log('{}');}
else if(args[0]==='server') {fs.writeFileSync(pid,''+process.pid);setInterval(()=>{},50);}
else if(args[0]==='run') {fs.writeFileSync(process.env.PB_LOGS+'/cli-args.json',JSON.stringify(args));if(args.includes('--timeout')){console.log('{"status":"completed","sessionId":"fixture-session"}');process.exit(0);}process.on('SIGINT',()=>{console.log('{"status":"aborted","sessionId":"fixture-session"}');process.exit(1);});setInterval(()=>{},50);}
else console.log('{}');
''');cli.chmod(0o755)
            env=dict(os.environ,PATH=str(Path(shutil.which('node')).parent)+os.pathsep+os.environ['PATH'],
                PENGUIN_HOME=str(home),PB_PREFIX=str(prefix),PB_LOGS=str(logs),PB_PROJECT='p',PB_AGENT='a',
                PB_PROVIDER='fixture',PB_MODEL='test',PB_THINKING='max',PB_TIMEOUT='1s',PB_ABORT_WAIT='1',
                PB_MAX_TURNS='',PB_DEADLINE_FILE=str(p/'deadline.json'))
            r=subprocess.run(['bash',str(ROOT/'agents/penguin_agent/run.sh')],cwd=workspace,env=env,capture_output=True,timeout=12)
            self.assertEqual(r.returncode,0,r.stderr)
            outcome=json.loads((logs/'penguin-outcome.json').read_text())
            self.assertTrue(outcome['timed_out'])
            self.assertEqual(outcome['status'],'timed_out')
            args=json.loads((logs/'cli-args.json').read_text())
            self.assertNotIn('--timeout',args)
            self.assertIn(str(workspace),args)
            receipt=json.loads((logs/'penguin/deadline.json').read_text())
            self.assertEqual(receipt['deadline_ms'],json.loads((p/'deadline.json').read_text())['deadline_ms'])
            # Existing tasks do not opt in and retain the CLI's relative timeout.
            env['PB_DEADLINE_FILE']=''
            r=subprocess.run(['bash',str(ROOT/'agents/penguin_agent/run.sh')],cwd=workspace,env=env,capture_output=True,timeout=12)
            self.assertEqual(r.returncode,0,r.stderr)
            args=json.loads((logs/'cli-args.json').read_text())
            self.assertEqual(args[args.index('--timeout')+1],'1s')
            self.assertFalse(json.loads((logs/'penguin-outcome.json').read_text())['timed_out'])

    def test_opt_in_shell_contract_leaves_default_timeout_path(self):
        text=(ROOT/'agents/penguin_agent/run.sh').read_text()
        self.assertIn('"$PB_PREFIX/deadline.mjs"',text)
        self.assertIn('elif [ -n "${PB_TIMEOUT:-}" ]',text)
        self.assertIn('TIMEOUT_ARGS=(--timeout "$PB_TIMEOUT")',text)
        self.assertLess(text.index('set-max-turns'),text.index('"$PB_PREFIX/deadline.mjs"'))


if __name__ == '__main__': unittest.main()
