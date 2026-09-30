import fs from 'node:fs';
import vm from 'node:vm';
import assert from 'node:assert/strict';
let passed=0;
for(const file of ['growth-suite.js','enterprise-suite.js']){
 const source=fs.readFileSync(new URL('../assets/'+file,import.meta.url),'utf8').split('\n').find(x=>x.trim().startsWith('async function api('));
 assert.ok(source,'Actual UI API function available');
 for(const mode of ['lost-response','invalid-json','server-error','read-failover','rejected']){
  let requests=0,resolutions=0;const resolve=async()=>({activeApiUrl:++resolutions===1?'http://primary.test/api.php':'http://standby.test/api.php',conflict:false});
  const context=vm.createContext({URL,Date,JSON,Error,sessionStorage:{getItem:()=>''},deviceId:()=> 'fixture',token:()=>'',operationId:()=> 'stable-op',oid:()=> 'stable-op',resolveEndpoint:resolve,resolve,fetch:async()=>{
   requests++;
   if(requests===1&&(mode==='lost-response'||mode==='read-failover'))throw Error('Network response lost after server commit');
   const status=mode==='server-error'?500:mode==='rejected'?422:200;
   return {status,ok:status===200,text:async()=>mode==='invalid-json'?'truncated':JSON.stringify({success:status===200,error:status===200?undefined:'fixture rejection'})};
  }});
  vm.runInContext(source,context);
  if(mode==='read-failover'){
   const result=await context.api('overview');assert.equal(result.success,true);assert.equal(requests,2);
  }else{
   await assert.rejects(context.api('save',{method:'POST',body:{amount:12.34}}),e=>mode==='rejected'?e.httpStatus===422:e.uncertain===true&&e.operationId==='stable-op');
   assert.equal(requests,1,'Uncertain write must not be resent to a different server');assert.equal(resolutions,1);
  }
  console.log('PASS '+file+' '+mode);passed++;
 }
}
const growth=fs.readFileSync(new URL('../assets/growth-suite.js',import.meta.url),'utf8').split('\n');
for(const count of [1,2]){
 const candidates=Array.from({length:count},(_,i)=>({apiUrl:`http://node${i}.test/api.php`,label:`node${i}`}));
 const delays=[];
 const context=vm.createContext({URL,Date,JSON,Error,AbortController,clearTimeout,
  setTimeout:(fn,ms)=>{delays.push(ms);return setTimeout(fn,ms);},
  endpointState:{cache:null,pending:null},state:{},renderServerPill:()=>{},normalizeApiUrl:x=>x,
  endpointCandidates:()=>candidates,sessionStorage:{getItem:()=>'',setItem:()=>{}},
  fetch:(_url,{signal})=>new Promise((resolve,reject)=>{
   const t=setTimeout(()=>resolve({ok:true,json:async()=>({success:true,databaseConnected:true,hotelScopeId:'fixture',nodeId:'same-node',cluster:{enabled:false,isPrimaryWriter:true}})}),10);
   signal.addEventListener('abort',()=>{clearTimeout(t);reject(Error('Probe aborted'));},{once:true});
  })});
 vm.runInContext(growth.find(x=>x.trim().startsWith('async function probeEndpoint('))+'\n'+growth.find(x=>x.trim().startsWith('async function resolveEndpoint(')),context);
 const resolved=await context.resolveEndpoint(true);
 assert.equal(resolved.activeApiUrl,candidates[0].apiUrl);
 assert.deepEqual(delays,Array(count).fill(1500),'Array.map index must not become probe timeout');
 assert.ok(resolved.probes.every(x=>x.reachable));
 console.log(`PASS Growth endpoint probe preserves timeout for ${count} candidate(s)`);passed++;
}
console.log(JSON.stringify({assertions:passed,passed}));
