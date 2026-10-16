// Optional read-only acceptance against a running panel with cross-day and stale records.
import {spawn} from 'node:child_process';
import {mkdtemp,readFile,rm,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
const output=process.argv[2];
if(!output)throw Error('Usage: node tests/e2e_dashboard_browser.mjs REPORT.json');
const profile=await mkdtemp(join(tmpdir(),'footprint-browser-'));
const chrome=spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',['--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--disable-extensions','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],{stdio:'ignore'});
let ws;const report={result:'fail',url:'http://127.0.0.1:8766/',viewport:{width:390,height:844},runtime_errors:[]};
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
try{
 let port;
 for(let i=0;i<100;i++){try{port=(await readFile(join(profile,'DevToolsActivePort'),'utf8')).split('\n')[0];break}catch{}await sleep(100)}
 if(!port)throw Error('Chrome did not expose its temporary debug port');
 const targets=await(await fetch('http://127.0.0.1:'+port+'/json')).json();
 ws=new WebSocket(targets.find(t=>t.type==='page').webSocketDebuggerUrl);
 await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j});
 let id=0;const pending=new Map();
 ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.id){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(Error(m.error.message)):p.resolve(m.result)}else if(m.method==='Runtime.exceptionThrown')report.runtime_errors.push(m.params.exceptionDetails.text)};
 const send=(method,params={})=>new Promise((resolve,reject)=>{const n=++id;pending.set(n,{resolve,reject});ws.send(JSON.stringify({id:n,method,params}))});
 const evaluate=async expression=>{const r=await send('Runtime.evaluate',{expression,returnByValue:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.text);return r.result.value};
 await send('Runtime.enable');await send('Page.enable');
 await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:false});
 await send('Page.navigate',{url:report.url});
 let ready=false;for(let i=0;i<100;i++){ready=await evaluate('typeof data!=="undefined" && data!==null');if(ready)break;await sleep(100)}
 if(!ready)throw Error('Dashboard metadata did not load');
 report.overview=await evaluate('({columns:document.querySelectorAll(".disk-summary").length,health:document.querySelector("#health").innerText,overflow:document.documentElement.scrollWidth>innerWidth,error:!document.querySelector("#error").hidden})');
 if(report.overview.columns!==2||report.overview.error||report.overview.overflow)throw Error('narrow dashboard presentation failed');
 await evaluate('document.querySelector("[data-tab=daily]").click()');
 report.daily=await evaluate('({reports:document.querySelectorAll(".report-day").length,cross_day:document.querySelector("#content").innerText.includes("跨日"),stale:document.querySelector("#content").innerText.includes("记录已过期"),unknown:document.querySelector("#content").innerText.includes("增长未知")})');
 if(!report.daily.reports||!report.daily.cross_day)throw Error('actual daily report did not display cross-day evidence');
 await evaluate('document.querySelector("[data-tab=projects]").click()');
 report.projects=await evaluate('({rows:document.querySelectorAll("tbody tr").length,stale:document.querySelector("#content").innerText.includes("记录已过期")})');
 if(report.runtime_errors.length||!report.projects.rows||!report.projects.stale)throw Error('coverage presentation failed');
 report.result='pass';
}catch(e){report.error=String(e);process.exitCode=1}
finally{if(ws)ws.close();chrome.kill('SIGTERM');await Promise.race([new Promise(r=>chrome.once('exit',r)),sleep(3000)]);if(chrome.exitCode===null)chrome.kill('SIGKILL');await sleep(200);await rm(profile,{recursive:true,force:true});report.temporary_profile_removed=true;await writeFile(output,JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report))}
