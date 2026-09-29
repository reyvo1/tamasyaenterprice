import fs from 'node:fs';
import path from 'node:path';
import vm from 'node:vm';
import assert from 'node:assert/strict';
import {fileURLToPath} from 'node:url';
const root=process.argv[2]||path.resolve(path.dirname(fileURLToPath(import.meta.url)),'..');
let passed=0,failed=0;
async function test(name,fn){try{await fn();passed++;console.log(`PASS ${name}`);}catch(e){failed++;console.log(`FAIL ${name}: ${e.message}`);}}
function worker(scope){
 const events={},puts=[],deletes=[];
 const cache={match:async()=>undefined,put:async(...args)=>puts.push(args),addAll:async()=>{}};
 const context=vm.createContext({URL,Response,Set,encodeURIComponent,
 self:{registration:{scope},location:{origin:'https://hotel.test'},addEventListener:(name,fn)=>events[name]=fn,clients:{claim:async()=>{}},skipWaiting:()=>{}},
 caches:{open:async()=>cache,keys:async()=>['tamasya-cache-'+encodeURIComponent('/other/')+'-r4.3-20260914'],delete:async name=>deletes.push(name),match:cache.match},
 fetch:async()=>({ok:true,type:'basic',headers:new Headers(),clone:()=>({})})});
 vm.runInContext(fs.readFileSync(path.join(root,'sw.js'),'utf8'),context);
 return {context,events,puts,deletes};
}
for(const resource of ['admin.php','webpublic/index.html','uploads/identity/photo.jpg','missing.html'])await test(`SW bypasses ${resource}`,()=>{
 const w=worker('https://hotel.test/app/');let intercepted=false;
 w.events.fetch({request:{url:'https://hotel.test/app/'+resource,method:'GET',headers:new Headers(),mode:'navigate'},respondWith:()=>intercepted=true});
 assert.equal(intercepted,false);
});
await test('SW cache differs between property subfolders',()=>{const a=worker('https://hotel.test/a/'),b=worker('https://hotel.test/b/');assert.notEqual(vm.runInContext('CACHE_NAME',a.context),vm.runInContext('CACHE_NAME',b.context));});
await test('SW activation retains another property cache',async()=>{const w=worker('https://hotel.test/app/');let done;w.events.activate({waitUntil:p=>done=p});await done;assert.equal(w.deletes.length,0);});
await test('SW still handles application entry navigation',async()=>{const w=worker('https://hotel.test/app/');let done;const waits=[];w.events.fetch({request:{url:'https://hotel.test/app/',method:'GET',mode:'navigate',headers:new Headers()},respondWith:p=>done=p,waitUntil:p=>waits.push(p)});assert.ok(done);await done;await Promise.all(waits);assert.equal(w.puts.length,1);});
await test('Enterprise navigation caches the fetched response with exactly two arguments',async()=>{
 const w=worker('https://hotel.test/app/');let done;const waits=[];
 w.events.fetch({request:{url:'https://hotel.test/app/enterprise-suite.html',method:'GET',mode:'navigate',headers:new Headers()},respondWith:p=>done=p,waitUntil:p=>waits.push(p)});
 assert.ok(done);await done;await Promise.all(waits);
 assert.equal(w.puts.length,1);assert.equal(w.puts[0].length,2);
 assert.equal(w.puts[0][0],'./enterprise-suite.html');assert.equal(typeof w.puts[0][1],'object');
});
function guard(status,payload){
 const calls=[],storage=new Map();
 const context=vm.createContext({URL,Headers,Request,Response,URLSearchParams,FormData,Blob,File,ArrayBuffer,Uint8Array,Date,Map,Set,JSON,Math,
 location:new URL('https://hotel.test/app/'),sessionStorage:{getItem:k=>storage.get(k),setItem:(k,v)=>storage.set(k,v),removeItem:k=>storage.delete(k)},
 window:{fetch:async(input,init)=>{calls.push(init);return new Response(JSON.stringify(payload),{status,headers:{'Content-Type':'application/json'}});}}});
 vm.runInContext(fs.readFileSync(path.join(root,'assets/api-operation-guard.js'),'utf8'),context);
 return {calls,fetch:()=>context.window.fetch('https://hotel.test/app/api.php?action=bookings',{method:'POST',body:'{"value":1}'})};
}
await test('202 response remains retryable with the same operation ID',async()=>{const g=guard(202,{success:true,pending:true});await g.fetch();const second=await g.fetch();assert.equal(second.status,202);assert.equal(g.calls.length,2);assert.equal(g.calls[0].headers.get('X-Tamasya-Operation-ID'),g.calls[1].headers.get('X-Tamasya-Operation-ID'));});
await test('business failure in HTTP 200 does not arm success shield',async()=>{const g=guard(200,{success:false});await g.fetch();await g.fetch();assert.equal(g.calls.length,2);});
await test('successful duplicate is still blocked',async()=>{const g=guard(200,{success:true});await g.fetch();assert.equal((await g.fetch()).status,409);assert.equal(g.calls.length,1);});
await test('503 retry retains the operation ID',async()=>{const g=guard(503,{success:false});await g.fetch();await g.fetch();assert.equal(g.calls.length,2);assert.equal(g.calls[0].headers.get('X-Tamasya-Operation-ID'),g.calls[1].headers.get('X-Tamasya-Operation-ID'));});
console.log(`${passed} passed; ${failed} failed`);process.exitCode=failed?1:0;
