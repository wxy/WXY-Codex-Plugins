// Black-box browser acceptance against a disposable panel, never the personal panel.
import {spawn} from 'node:child_process';
import {mkdtemp,readFile,rm,writeFile} from 'node:fs/promises';
import {tmpdir} from 'node:os';
import {join} from 'node:path';
const [url,output]=process.argv.slice(2);
if(!url||!output)throw Error('Usage: node e2e_cache_dashboard.mjs FIXTURE_URL REPORT.json');
const profile=await mkdtemp(join(tmpdir(),'footprint-cache-browser-'));
const chrome=spawn('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',['--headless=new','--disable-gpu','--no-first-run','--no-default-browser-check','--disable-extensions','--remote-debugging-port=0','--user-data-dir='+profile,'about:blank'],{stdio:'ignore'});
const sleep=ms=>new Promise(r=>setTimeout(r,ms));
let ws;const report={result:'fail',viewport:{width:390,height:844},runtime_errors:[]};
try{
 let port;for(let i=0;i<100;i++){try{port=(await readFile(join(profile,'DevToolsActivePort'),'utf8')).split('\n')[0];break}catch{}await sleep(100)}
 if(!port)throw Error('temporary Chrome did not start');
 const tabs=await(await fetch('http://127.0.0.1:'+port+'/json')).json();
 ws=new WebSocket(tabs.find(t=>t.type==='page').webSocketDebuggerUrl);await new Promise((r,j)=>{ws.onopen=r;ws.onerror=j});
 let id=0;const pending=new Map();
 ws.onmessage=e=>{const m=JSON.parse(e.data);if(m.id){const p=pending.get(m.id);pending.delete(m.id);m.error?p.reject(Error(m.error.message)):p.resolve(m.result)}else if(m.method==='Runtime.exceptionThrown')report.runtime_errors.push(m.params.exceptionDetails.text)};
 const send=(method,params={})=>new Promise((resolve,reject)=>{const n=++id;pending.set(n,{resolve,reject});ws.send(JSON.stringify({id:n,method,params}))});
 const evaluate=async expression=>{const r=await send('Runtime.evaluate',{expression,returnByValue:true});if(r.exceptionDetails)throw Error(r.exceptionDetails.text);return r.result.value};
 await send('Runtime.enable');await send('Page.enable');await send('Emulation.setDeviceMetricsOverride',{width:390,height:844,deviceScaleFactor:1,mobile:false});
 await send('Page.navigate',{url});
 let ready=false;for(let i=0;i<100;i++){ready=await evaluate('typeof data!=="undefined" && data!==null');if(ready)break;await sleep(100)}
 if(!ready)throw Error('fixture panel not ready');
 const check=()=>evaluate('({gaps:document.querySelectorAll(".cache-gap").length,unknown:document.querySelector("#content").innerText.includes("占用与增长未知"),scope:document.querySelector("#content").innerText.includes("其他可读应用缓存"),overflow:document.documentElement.scrollWidth>innerWidth,error:!document.querySelector("#error").hidden})');
 report.overview=await check();
 await evaluate('document.querySelector("[data-tab=projects]").click()');report.projects=await check();
 await evaluate('document.querySelector("[data-tab=daily]").click()');report.daily=await check();
 for(const row of [report.overview,report.projects,report.daily])if(!row.gaps||!row.unknown||!row.scope||row.overflow||row.error)throw Error('cache coverage presentation failed');
 if(report.runtime_errors.length)throw Error('browser exception');report.result='pass';
}catch(e){report.error=String(e);process.exitCode=1}
finally{if(ws)ws.close();chrome.kill('SIGTERM');await Promise.race([new Promise(r=>chrome.once('exit',r)),sleep(3000)]);if(chrome.exitCode===null)chrome.kill('SIGKILL');await sleep(200);await rm(profile,{recursive:true,force:true});report.temporary_profile_removed=true;await writeFile(output,JSON.stringify(report,null,2)+'\n');console.log(JSON.stringify(report))}
