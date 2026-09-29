import {test,expect} from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
const fixture=process.env.TAMASYA_UAT_FIXTURE;
if(!fixture)throw Error('Dedicated UAT fixture required');
const env=JSON.parse(fs.readFileSync(path.join(fixture,'environment.json'),'utf8'));
const base='http://127.0.0.1:38189';
test.beforeEach(async({page,request})=>{
  // Block all nonlocal browser egress (providers/CDNs must never receive fixture data).
  await page.route('**/*',route=>{
    const u=new URL(route.request().url());
    return ['127.0.0.1','localhost'].includes(u.hostname)?route.continue():route.abort();
  });
  const r=await request.post('/api.php?action=login',{headers:{Origin:base,'X-Device-ID':'uat-browser'},
    data:{username:env.APP_BOOTSTRAP_ADMIN_USERNAME,password:env.APP_BOOTSTRAP_ADMIN_PASSWORD}});
  expect(r.status()).toBe(200);const session=await r.json();expect(session.token).toBeTruthy();
  await page.addInitScript(({token,base})=>{
    sessionStorage.setItem('hotel_logged_in','true');sessionStorage.setItem('hotel_session_token',token);
    sessionStorage.setItem('hotel_staff_role','admin');sessionStorage.setItem('hotel_role','admin');
    sessionStorage.setItem('tamasya_active_api_url',base+'/api.php');localStorage.setItem('hotel_device_id','uat-browser');
  },{token:session.token,base});
});
for(const file of ['growth-suite.html','enterprise-suite.html']){
  test(`${file}: every rendered module tab changes visible panel`,async({page},info)=>{
    const errors=[];page.on('pageerror',e=>errors.push(e.message));
    await page.goto('/'+file);await expect(page.locator('#tabs')).toBeVisible();
    await expect(page.locator('#loading')).toBeHidden();
    const tabs=await page.locator('#tabs [data-tab]').evaluateAll(xs=>xs.map(x=>x.dataset.tab));
    expect(tabs.length).toBeGreaterThan(0);
    const evidence=[];
    for(const tab of tabs){
      await page.locator(`#tabs [data-tab="${tab}"]`).click();
      await expect(page.locator(`#tab-${tab}`)).toBeVisible();
      const controls=await page.locator(`#tab-${tab} button, #tab-${tab} input, #tab-${tab} select`).evaluateAll(xs=>xs.map(x=>({tag:x.tagName,id:x.id,type:x.type||'',text:(x.innerText||'').slice(0,120)})));
      evidence.push({page:file,tab,assertion:'panel becomes visible',pass:true,discoveredControls:controls,controlsBehaviorTested:false});
    }
    expect(errors).toEqual([]);
    fs.writeFileSync(`artifacts/browser-${info.project.name}-${file}.json`,JSON.stringify(evidence,null,2));
  });
}
test('Enterprise purchase request: browser submit persists draft',async({page,request},info)=>{
  await page.goto('/enterprise-suite.html');await expect(page.locator('#loading')).toBeHidden();
  await page.locator('[data-tab="ap"]').click();
  const item=`UAT browser ${info.project.name} ${Date.now()}`;
  await page.locator('#pr-item').fill(item);await page.locator('#pr-qty').fill('2');await page.locator('#pr-price').fill('12000');
  const response=page.waitForResponse(r=>r.url().includes('action=enterprise-suite')&&r.request().method()==='POST'&&r.request().postData()?.includes('pr-save'));
  await page.locator('#pr-form button[type="submit"]').click();
  const r=await response;expect(r.status()).toBe(200);const d=await r.json();expect(d.success).toBe(true);
  expect(d.data.request.id).toBeTruthy();expect(d.data.request.status).toBe('draft');
  await page.reload();await expect(page.locator('#loading')).toBeHidden();await page.locator('[data-tab="ap"]').click();
  await expect(page.locator('#pr-list')).toContainText(d.data.request.request_number || d.data.request.pr_number || 'draft');
  fs.writeFileSync(`artifacts/browser-pr-${info.project.name}.json`,JSON.stringify({test:'browser PR submit and reload',pass:true,requestId:d.data.request.id,scope:'PR draft only; approval/posting covered separately via API, not claimed as UI-tested'}));
});
