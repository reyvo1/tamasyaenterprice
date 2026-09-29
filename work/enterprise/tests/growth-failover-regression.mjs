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
console.log(JSON.stringify({assertions:passed,passed}));
