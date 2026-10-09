#!/usr/bin/env python3
"""Black-box system/development disk scope and capacity-chart regression acceptance."""
import argparse
import json
import os
from pathlib import Path
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import time
import traceback
import urllib.request

ENTRY=Path(os.environ.get('CODEX_FOOTPRINT_TEST_ENTRY',str(Path(__file__).resolve().parents[1]/'scripts/codex_footprint.py'))).resolve()
PRIMARY='/System/Volumes/Data' if sys.platform=='darwin' else '/'


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--output',required=True);ap.add_argument('--browser',action='store_true');args=ap.parse_args()
    out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=True)
    report={'command':[sys.executable,str(Path(__file__).resolve()),'--output',str(out)]+(['--browser'] if args.browser else []),
            'environment':{'python':sys.version,'platform':sys.platform},
            'preconditions':'Local Python/SQLite, subprocesses and loopback. External-scope case uses a mounted /Volumes/MacSSD read-only; optional browser needs Node, Playwright and Chromium (NODE_PATH, CODEX_FOOTPRINT_TEST_NODE and CODEX_FOOTPRINT_TEST_CHROME may select installed dependencies). No personal state, model calls or notifications.',
            'inputs':'Temporary internal workspace/config/database. Seeded minute records for the internal data mount across changed device IDs, stale external-volume records, one-minute late start, and external paths/parent symlinks without traversing or writing external files.', 'cases':[]}
    def case(name,fn):
        with tempfile.TemporaryDirectory(prefix='footprint-internal-chart-e2e-') as directory:
            tmp=Path(directory).resolve();work=tmp/'workspace';work.mkdir();state=tmp/'state';processes=[]
            env=dict(os.environ,CODEX_HOME=str(tmp/'codex'),CODEX_FOOTPRINT_DATA=str(state),CODEX_FOOTPRINT_CONFIG=str(state/'config.json'),PYTHONDONTWRITEBYTECODE='1')
            def run(*argv,input=None):
                p=subprocess.run([sys.executable,str(ENTRY),*argv],env=env,input=input,text=True,capture_output=True,timeout=30)
                assert p.returncode==0 and not p.stderr,(argv,p.stderr)
                return json.loads(p.stdout) if p.stdout.strip() else None
            run('enable','--root',str(work),'--no-defaults','--no-start','--notifications','inbox')
            def panel():
                p=subprocess.Popen([sys.executable,str(ENTRY),'panel','--port','0'],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL);processes.append(p)
                deadline=time.monotonic()+5
                while time.monotonic()<deadline:
                    info=state/'panel.json'
                    if info.exists():
                        url=json.loads(info.read_text()).get('url')
                        if url:return url
                    time.sleep(.05)
                raise AssertionError('panel not ready')
            def get(url,window):
                with urllib.request.urlopen(url+'api/dashboard?range='+window,timeout=5) as r:return json.load(r)
            try:
                evidence=fn(tmp,work,state,env,run,panel,get)
                report['cases'].append({'name':name,'result':'pass','evidence':evidence})
            except Exception:report['cases'].append({'name':name,'result':'fail','error':traceback.format_exc()})
            finally:
                for p in processes:
                    if p.poll() is None:p.terminate()
                    try:p.wait(timeout=5)
                    except subprocess.TimeoutExpired:p.kill();p.wait(timeout=5)
        assert not tmp.exists()
    def external(tmp,work,state,env,run,panel,get):
        external=Path('/Volumes/MacSSD')
        if not external.exists() or external.stat().st_dev==Path(PRIMARY).stat().st_dev:
            return {'real_external_volume':'unavailable; real-mount assertion skipped'}
        alias=tmp/'external-parent';alias.symlink_to(external,target_is_directory=True)
        config=json.loads((state/'config.json').read_text());config['monitor']['development_volume']=str(external);missing='develop/footprint-missing-e2e';config['roots'] += [{'path':str(external/missing)},{'path':str(alias/missing)},{'path':'/Volumes/unselected-drive/project'}];(state/'config.json').write_text(json.dumps(config))
        # Check admission before any tick, so the failing old runtime never scans the real external volume.
        before=run('status');assert set(before['configured_roots'])=={str(work),str(external/missing)},before['configured_roots']
        run('hook',input=json.dumps({'hook_event_name':'PreToolUse','session_id':'external','cwd':str(alias/missing),'tool_name':'Bash'}))
        run('tick','--rounds','2');status=run('status')
        assert set(status['configured_roots'])=={str(work),str(external/missing)} and status['event_count']==1,status
        assert {r['path'] for r in status['volumes']}=={PRIMARY,str(external)},status['volumes']
        assert status['coverage']['storage_scope']=='system_and_development_volumes'
        return {'selected_development_disk_and_parent_alias_coalesce':True,'other_external_disks_excluded':True,'capacity_sampled_separately':True,'missing_external_fixture_not_traversed':True}
    case('selected_development_volume_and_other_external_exclusion',external)
    def seed(state,run,short=False):
        config=json.loads((state/'config.json').read_text());config['monitor']['development_volume']='/Volumes/MacSSD';(state/'config.json').write_text(json.dumps(config))
        run('tick');now=time.time();device=Path(PRIMARY).stat().st_dev
        ages=[40,10] if short else [3*86400,20*3600,3*3600,30*60,10*60]
        with sqlite3.connect(state/'global.sqlite3') as db:
            db.execute('DELETE FROM volume_minutes');db.execute('DELETE FROM volumes')
            outside={'path':'/Volumes/stale-external','device':987654,'available_bytes':900000000000,'total_bytes':1000000000000,'sampled_at':now-5}
            development=dict(outside,path='/Volumes/MacSSD',device=987655)
            db.execute('INSERT INTO volumes VALUES(?,?)',(development['path'],json.dumps(development)))
            internal={'path':PRIMARY,'device':device,'available_bytes':51000000000,'total_bytes':245000000000,'sampled_at':now-10}
            db.execute('INSERT INTO volumes VALUES(?,?)',(outside['path'],json.dumps(outside)))
            db.execute('INSERT INTO volumes VALUES(?,?)',(internal['path'],json.dumps(internal)))
            for i,age in enumerate(ages):
                ts=now-age;row=dict(internal,device=device if short else device+100+i,available_bytes=51000000000+i*100000000,sampled_at=ts)
                # Separate buckets for the short case: preserve a real 30-second span across a minute boundary.
                if short:ts=int((now-35)//60)*60+(-10 if i==0 else 20);row['sampled_at']=ts
                db.execute('INSERT OR REPLACE INTO volume_minutes VALUES(?,?,?,?)',(row['device'],int(ts//60),ts,json.dumps(row)))
            for i,age in enumerate(ages):
                ts=(int((now-35)//60)*60+(-10 if i==0 else 20)) if short else now-age
                row=dict(development,available_bytes=900000000000-i*100000000,sampled_at=ts)
                db.execute('INSERT OR REPLACE INTO volume_minutes VALUES(?,?,?,?)',(row['device'],int(ts//60),ts,json.dumps(row)))
            db.execute('INSERT OR REPLACE INTO volume_minutes VALUES(?,?,?,?)',(outside['device'],int((now-5)//60),now-5,json.dumps(outside)))
        return device
    def ranges(tmp,work,state,env,run,panel,get):
        seed(state,run);url=panel();values={k:get(url,k) for k in ('1h','24h','7d')}
        counts={k:len(v['volume_history']) for k,v in values.items()}
        assert counts['1h']<counts['24h']<counts['7d'],counts
        for window,seconds in (('1h',3600),('24h',86400),('7d',604800)):
            value=values[window];assert [r['path'] for r in value['volumes']]==[PRIMARY,'/Volumes/MacSSD'],value['volumes']
            assert len(value['capacity_charts'])==2
            assert value['capacity_charts'][0]['complete_roots']==1 and value['capacity_charts'][1]['complete_roots']==0
            assert all(r['path']==PRIMARY for r in value['volume_history'])
            assert abs(value['chart_window']['requested_to']-value['chart_window']['requested_from']-seconds)<.01
        assert values['7d']['volume_history'][-1]['sampled_at']-values['7d']['volume_history'][0]['sampled_at']>2*86400
        with sqlite3.connect(state/'global.sqlite3') as db:assert db.execute('SELECT count(*) FROM volumes').fetchone()[0]==3
        return {'range_samples':counts,'internal_history_survives_device_id_change':True,'stale_external_rows_hidden_but_preserved':True}
    case('chart_ranges_internal_selection_and_changed_device_ids',ranges)
    def summary(tmp,work,state,env,run,panel,get):
        seed(state,run)
        with sqlite3.connect(state/'global.sqlite3') as db:
            outside={'path':'/Volumes/stale-external','kind':'growth','growth_bytes':999999999,'latest_at':time.time()}
            db.execute('INSERT INTO alerts(fingerprint,ts,payload) VALUES(?,?,?)',('outside',time.time(),json.dumps(outside)))
        result=run('daily-report');assert [r['path'] for r in result['volumes']]==[PRIMARY,'/Volumes/MacSSD']
        assert not result['alerts'] and not result['full_disk_scan_triggered']
        assert not run('alerts')['alerts']
        return {'daily_summary_and_alerts_follow_selected_disks':True,'no_scan_or_history_analysis':True}
    case('summary_and_alerts_exclude_external_history',summary)
    if args.browser:
        def browser(tmp,work,state,env,run,panel,get):
            seed(state,run,short=True);url=panel();script=tmp/'browser.cjs'
            script.write_text('''const {chromium}=require('playwright');
(async()=>{const browser=await chromium.launch({headless:true,executablePath:process.env.CODEX_FOOTPRINT_TEST_CHROME||undefined});
try {const page=await browser.newPage();const evidence=[];
for (const width of [400,1100]) {await page.setViewportSize({width,height:950});await page.goto(process.argv[2]);
for (const range of ['1h','24h','7d']) {await page.locator('[data-range="'+range+'"]').click();
await page.waitForFunction(r=>document.querySelectorAll('.disk-summary').length===2 && [...document.querySelectorAll('.chart-labels')].every(x=>x.dataset.range===r),range);
const result=await page.evaluate(()=>{const labels=document.querySelector('.chart-labels');const line=document.querySelector('.chart polyline');const xs=line?line.getAttribute('points').split(' ').map(p=>Number(p.split(',')[0])):[];
return {range:labels.dataset.range,from:Number(labels.dataset.from),to:Number(labels.dataset.to),labels:[...labels.children].map(x=>x.textContent),diskColumns:document.querySelectorAll('.disk-summary').length,metricCards:document.querySelectorAll('.disk-summary .card').length,span:xs.length?Math.max(...xs)-Math.min(...xs):0,overflow:document.documentElement.scrollWidth>innerWidth+1,coverage:document.querySelector('.chart-coverage').textContent}});
const duration={"1h":3600,"24h":86400,"7d":604800}[range];
if(Math.abs(result.to-result.from-duration)>.1||result.labels.length<3||result.diskColumns!==2||result.metricCards!==8||result.span>20||result.overflow)throw Error(JSON.stringify({width,...result}));
if(!result.coverage.includes('没有记录'))throw Error('missing coverage text');
evidence.push({width,...result});}}
console.log(JSON.stringify(evidence));} finally {await browser.close();}})().catch(e=>{console.error(e);process.exitCode=1;});''')
            node=os.environ.get('CODEX_FOOTPRINT_TEST_NODE') or shutil.which('node');assert node,'Node required for browser acceptance'
            p=subprocess.run([node,str(script),url],env=env,text=True,capture_output=True,timeout=60)
            assert p.returncode==0,p.stderr
            return {'browser_range_axes_and_late_start':json.loads(p.stdout),'headless_browser_only':'actual in-app rendering remains a separate acceptance surface'}
        case('browser_selected_window_labels_and_sparse_coverage',browser)
    report['temporary_process_files_removed']=True;report['result']='pass' if all(r['result']=='pass' for r in report['cases']) else 'fail'
    (out/'report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({'result':report['result'],'cases':[{k:r[k] for k in ('name','result')} for r in report['cases']],'report':str(out/'report.json')}));return report['result']!='pass'
if __name__=='__main__':raise SystemExit(main())
