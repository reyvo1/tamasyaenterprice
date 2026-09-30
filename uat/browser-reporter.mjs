import fs from 'node:fs';
// Never publish traces, request headers/bodies, page HTML, or arbitrary error text.
export default class SafeReporter {
  rows=[];
  onTestEnd(test,result){
    this.rows.push({title:test.titlePath().slice(1),status:result.status,
      expectedStatus:test.expectedStatus,durationMs:result.duration,
      location:{file:test.location.file.split('/').pop(),line:test.location.line},
      errorKinds:(result.errors||[]).map(e=>({
        timeout:/timeout|timed out/i.test(e.message||''),
        assertion:/expect\(|toBe|toHave|toEqual|toContain/.test(e.message||''),
        stackLocations:[...(e.stack||'').matchAll(/operational\.spec\.mjs:(\d+):(\d+)/g)].map(m=>({line:Number(m[1]),column:Number(m[2])}))
      }))});
    fs.mkdirSync('artifacts',{recursive:true});
    fs.writeFileSync('artifacts/browser-results.json',JSON.stringify(this.rows,null,2));
  }
}
