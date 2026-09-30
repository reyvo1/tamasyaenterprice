import {test,expect} from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';
const fixture=process.env.TAMASYA_UAT_FIXTURE;
if(!fixture)throw Error('Dedicated UAT fixture required');
const env=JSON.parse(fs.readFileSync(path.join(fixture,'environment.json'),'utf8'));
const base='http://127.0.0.1:28189';
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
for(const [file,marker] of [
  ['index.html','#root > *'],
  ['property-setup.html','h1'],
  ['interproperty-transfer.html','#status'],
  ['multi-property-foundation.html','h1'],
  ['hq/index.html','#login-form'],
  ['hq/control.html','#login-form'],
  ['webpublic/index.html','#root > *'],
]){
  test(`${file}: entrypoint renders without a browser exception`,async({page},info)=>{
    const errors=[];page.on('pageerror',error=>errors.push(error.message));
    const response=await page.goto('/'+file);
    expect(response?.status()).toBe(200);
    await expect(page.locator(marker).first()).toBeVisible();
    expect(errors).toEqual([]);
    const name=file.replaceAll('/','-');
    fs.writeFileSync(`artifacts/browser-entry-${info.project.name}-${name}.json`,JSON.stringify({page:file,assertion:'entrypoint rendered; no browser exception',pass:true,scope:'Navigation only; control behavior and live endpoints not verified'}));
  });
}
test('Property setup: save, refresh, persisted reload and restore',async({page},info)=>{
  await page.goto('/property-setup.html');
  const name=page.locator('#propertyName');
  await expect(name).toHaveValue(/.+/);
  const original=await name.inputValue();
  await expect(page.locator('#ready-text')).toContainText('Property sudah READY');
  const uatName=`UAT property ${info.project.name} ${Date.now()}`;
  const save=async value=>{
    await name.fill(value);
    const posted=page.waitForResponse(r=>r.url().includes('action=property-setup')&&r.url().includes('command=save')&&r.request().method()==='POST');
    await page.locator('#save').click();
    const response=await posted;
    expect(response.status()).toBe(200);
    expect((await response.json()).success).toBe(true);
    await expect(name).toHaveValue(value);
  };
  await save(uatName);
  await page.reload();
  await expect(name).toHaveValue(uatName);
  const refreshed=page.waitForResponse(r=>r.url().includes('action=property-setup')&&r.url().includes('command=status'));
  await page.locator('#refresh').click();
  expect((await refreshed).status()).toBe(200);
  await expect(name).toHaveValue(uatName);
  await save(original);
  await expect(page.locator('#finalize')).toBeEnabled();
  const finalized=page.waitForResponse(r=>r.url().includes('action=property-setup')&&r.url().includes('command=finalize')&&r.request().method()==='POST');
  await page.locator('#finalize').click();
  const finalResponse=await finalized;
  expect(finalResponse.status()).toBe(200);
  expect((await finalResponse.json()).success).toBe(true);
  await page.reload();
  await expect(name).toHaveValue(original);
  await expect(page.locator('#ready-text')).toContainText('Property sudah READY');
  fs.writeFileSync(`artifacts/browser-setup-${info.project.name}.json`,JSON.stringify({test:'property settings save, refresh, persisted reload, restore and re-finalize',pass:true,scope:'Property name and READY transition only; other setup controls not claimed'}));
});
test('Multi-property readiness: read-only buttons render their server results',async({page},info)=>{
  await page.goto('/multi-property-foundation.html');
  await expect(page.locator('#status-cards .card')).toHaveCount(5);
  const clickAndRead=async(button,command)=>{
    const completed=page.waitForResponse(r=>r.url().includes('action=multi-property')&&r.url().includes(`command=${command}`));
    await page.locator(button).click();
    const response=await completed;
    expect(response.status()).toBe(200);
    const body=await response.json();
    expect(body.success).toBe(true);
    return body.data;
  };
  await clickAndRead('#refresh','overview');
  await expect(page.locator('#status-cards .card')).toHaveCount(5);
  await clickAndRead('#preview','summary-preview');
  await expect(page.locator('#preview-result .card')).toHaveCount(7);
  await expect(page.locator('#preview-result')).toContainText('Privacy:');
  await clickAndRead('#manifest','manifest');
  expect(JSON.parse(await page.locator('#manifest-result').innerText())).toEqual(expect.any(Object));
  await clickAndRead('#contracts','capabilities');
  expect(JSON.parse(await page.locator('#contract-result').innerText())).toEqual(expect.any(Object));
  await clickAndRead('#outbox','outbox');
  await expect(page.locator('#outbox-result')).toContainText('job;');
  fs.writeFileSync(`artifacts/browser-multi-property-${info.project.name}.json`,JSON.stringify({test:'multi-property overview, preview, manifest, capabilities and outbox read-only buttons',pass:true,scope:'Snapshot download/queue/push and dynamic outbox actions not claimed'}));
});
test('Multi-property snapshot: download aggregate, queue locally and reload outbox',async({page},info)=>{
  await page.goto('/multi-property-foundation.html');
  await expect(page.locator('#status-cards .card')).toHaveCount(5);
  const [snapshotResponse,download]=await Promise.all([
    page.waitForResponse(r=>r.url().includes('action=multi-property')&&r.url().includes('command=snapshot-v3')),
    page.waitForEvent('download'),
    page.locator('#snapshot-v2').click(),
  ]);
  expect(snapshotResponse.status()).toBe(200);
  const apiSnapshot=(await snapshotResponse.json()).data;
  const savedSnapshot=JSON.parse(fs.readFileSync(await download.path(),'utf8'));
  expect(savedSnapshot).toEqual(apiSnapshot);
  expect(savedSnapshot.contractVersion).toBe('tamasya-hq-snapshot-v3');
  expect(savedSnapshot.checksumSha256).toMatch(/^[a-f0-9]{64}$/);
  expect(savedSnapshot).not.toHaveProperty('bookings');
  expect(savedSnapshot).not.toHaveProperty('guests');
  const queued=page.waitForResponse(r=>r.url().includes('action=multi-property')&&r.request().method()==='POST'&&r.request().postData()?.includes('queue-snapshot'));
  await page.locator('#queue-snapshot').click();
  const queueResponse=await queued;
  expect(queueResponse.status()).toBe(202);
  const queueBody=await queueResponse.json();
  expect(queueBody.success).toBe(true);
  expect(queueBody.data.status).toBe('pending');
  const operation=queueBody.data.operation_id;
  expect(operation).toMatch(/^hq-/);
  await expect(page.locator('#outbox-result')).toContainText(operation);
  await page.reload();
  const listed=page.waitForResponse(r=>r.url().includes('action=multi-property')&&r.url().includes('command=outbox'));
  await page.locator('#outbox').click();
  expect((await listed).status()).toBe(200);
  await expect(page.locator('#outbox-result')).toContainText(operation);
  fs.writeFileSync(`artifacts/browser-snapshot-${info.project.name}.json`,JSON.stringify({test:'aggregate snapshot download and durable local outbox queue/reload',pass:true,scope:'No delivery to HQ and no ACK claimed'}));
});
test('Enterprise procurement: PR, PO, GRN and supplier invoice posting persist',async({page,request},info)=>{
  await page.goto('/enterprise-suite.html');await expect(page.locator('#loading')).toBeHidden();
  await page.locator('[data-tab="ap"]').click();
  const item=`UAT browser ${info.project.name} ${Date.now()}`;
  await page.locator('#pr-item').fill(item);await page.locator('#pr-qty').fill('2');await page.locator('#pr-price').fill('12000');
  const response=page.waitForResponse(r=>r.url().includes('action=enterprise-suite')&&r.request().method()==='POST'&&r.request().postData()?.includes('pr-save'));
  await page.locator('#pr-form button[type="submit"]').click();
  const r=await response;
  const d=await r.json();
  fs.writeFileSync(`artifacts/browser-pr-diagnostic-${info.project.name}.json`,JSON.stringify({httpStatus:r.status(),success:d.success===true,code:typeof d.code==='string'?d.code:null}));
  expect(r.status()).toBe(200);expect(d.success).toBe(true);
  expect(d.data.request.id).toBeTruthy();expect(d.data.request.status).toBe('draft');
  await page.reload();await expect(page.locator('#loading')).toBeHidden();await page.locator('[data-tab="ap"]').click();
  await expect(page.locator('#pr-list')).toContainText(d.data.request.request_number || d.data.request.pr_number || 'draft');
  for(const [button,status] of [['Submit','submitted'],['Approve','approved']]){
    const row=page.locator('#pr-list tr').filter({hasText:d.data.request.pr_number});
    const posted=page.waitForResponse(r=>r.url().includes('action=enterprise-suite')&&r.request().method()==='POST'&&r.request().postData()?.includes('pr-status'));
    await row.getByRole('button',{name:button,exact:true}).click();
    const r=await posted;expect(r.status()).toBe(200);expect((await r.json()).success).toBe(true);
    await expect(page.locator('#loading')).toBeHidden();
    await expect(page.locator('#pr-list tr').filter({hasText:d.data.request.pr_number})).toContainText(status);
  }
  await page.reload();await expect(page.locator('#loading')).toBeHidden();await page.locator('[data-tab="ap"]').click();
  await expect(page.locator('#pr-list tr').filter({hasText:d.data.request.pr_number})).toContainText('approved');
  await page.locator('#pr-list tr').filter({hasText:d.data.request.pr_number}).getByRole('button',{name:'Detail'}).click();
  await expect(page.locator('#pr-to-po')).toBeVisible();
  await expect(page.locator('#pr-vendor option')).not.toHaveCount(1);
  await page.locator('#pr-vendor').selectOption({index:1});
  const created=page.waitForResponse(r=>r.url().includes('action=enterprise-suite')&&r.request().method()==='POST'&&r.request().postData()?.includes('po-create-from-pr'));
  await page.locator('#pr-to-po').click();
  const poResponse=await created,poBody=await poResponse.json();
  expect(poResponse.status()).toBe(200);expect(poBody.success).toBe(true);
  const po=poBody.data;
  expect(po.status).toBe('draft');expect(Number(po.total_amount)).toBeGreaterThan(0);
  await expect(page.locator('#loading')).toBeHidden();
  await expect(page.locator('#po-list tr').filter({hasText:po.po_number})).toContainText('draft');

  const growthBoot=page.waitForResponse(r=>r.url().includes('action=growth-suite')&&r.url().includes('command=bootstrap'));
  await page.goto('/growth-suite.html');
  const growthResponse=await growthBoot;expect(growthResponse.status()).toBe(200);
  await expect(page.locator('#loading')).toBeHidden();
  await page.locator('[data-tab="procurement"]').click();
  await expect(page.locator('#po-list tr').filter({hasText:po.po_number})).toBeVisible();
  for(const [button,status] of [['Submit','submitted'],['Approve','approved']]){
    const action=page.locator('#po-list tr').filter({hasText:po.po_number}).getByRole('button',{name:button,exact:true});
    await expect(action).toBeVisible();await expect(action).toBeEnabled();
    await expect(page.locator('#loading')).toBeHidden();
    await action.evaluate(el=>el.scrollIntoView({block:'center',inline:'center'}));
    const target=await action.evaluate(el=>{const r=el.getBoundingClientRect(),x=r.left+r.width/2,y=r.top+r.height/2,hit=document.elementFromPoint(x,y);return{centerX:Math.round(x),centerY:Math.round(y),viewportWidth:innerWidth,viewportHeight:innerHeight,centerHitsButton:hit===el||el.contains(hit),hitTag:hit?.tagName||null,hitId:hit?.id||null}});
    fs.writeFileSync(`artifacts/browser-po-stage-${info.project.name}.json`,JSON.stringify({stage:`before-${status}`,buttonVisible:await action.isVisible(),buttonEnabled:await action.isEnabled(),loadingHidden:await page.locator('#loading').isHidden(),target}));
    const posted=page.waitForResponse(r=>r.url().includes('action=growth-suite')&&r.request().method()==='POST'&&r.request().postData()?.includes('po-status'));
    if(info.project.name==='mobile')await action.tap({timeout:15000});else await action.click({timeout:15000});
    const update=await posted,body=await update.json();
    expect(update.status()).toBe(200);expect(body.success).toBe(true);expect(body.data.status).toBe(status);
    await expect(page.locator('#po-list tr').filter({hasText:po.po_number})).toContainText(status);
    await expect(page.locator('#po-detail')).toContainText(po.po_number);
    await expect(page.locator('#po-detail')).toContainText(status);
    await expect(page.locator('#loading')).toBeHidden();
    fs.writeFileSync(`artifacts/browser-po-stage-${info.project.name}.json`,JSON.stringify({stage:`after-${status}`,httpStatus:update.status(),detailComplete:true,loadingHidden:true}));
  }
  await page.reload();await expect(page.locator('#loading')).toBeHidden();await page.locator('[data-tab="procurement"]').click();
  await expect(page.locator('#po-list tr').filter({hasText:po.po_number})).toContainText('approved');

  await page.goto('/enterprise-suite.html');await expect(page.locator('#loading')).toBeHidden();await page.locator('[data-tab="ap"]').click();
  await page.locator('#po-list tr').filter({hasText:po.po_number}).getByRole('button',{name:'Buat GRN'}).click();
  await expect(page.locator('#grn-work')).toContainText(item);
  await expect(page.locator('[data-grn-item]')).toHaveValue('2');
  const drafted=page.waitForResponse(r=>r.url().includes('action=enterprise-suite')&&r.request().method()==='POST'&&r.request().postData()?.includes('grn-save'));
  await page.locator('#create-grn-now').click();
  const grnResponse=await drafted,grnBody=await grnResponse.json();
  expect(grnResponse.status()).toBe(200);expect(grnBody.success).toBe(true);
  expect(grnBody.data.receipt.status).toBe('draft');
  const grn=grnBody.data.receipt;
  await expect(page.locator('#grn-work')).toContainText(grn.grn_number);
  const posted=page.waitForResponse(r=>r.url().includes('action=enterprise-suite')&&r.request().method()==='POST'&&r.request().postData()?.includes('grn-post'));
  await page.locator('#post-grn-now').click();
  const postedResponse=await posted,postedBody=await postedResponse.json();
  expect(postedResponse.status()).toBe(200);expect(postedBody.success).toBe(true);
  expect(postedBody.data.receipt.status).toBe('posted');
  await expect(page.locator('#loading')).toBeHidden();
  await expect(page.locator('#po-list tr').filter({hasText:po.po_number})).toContainText('received');
  await expect(page.locator('#sinv-grn')).toContainText(grn.grn_number);
  await page.reload();await expect(page.locator('#loading')).toBeHidden();await page.locator('[data-tab="ap"]').click();
  await expect(page.locator('#po-list tr').filter({hasText:po.po_number})).toContainText('received');
  await expect(page.locator('#sinv-grn')).toContainText(grn.grn_number);
  await page.locator('#sinv-po').selectOption(po.id);
  await expect(page.locator('#sinv-po-item option')).not.toHaveCount(1);
  await page.locator('#sinv-po-item').selectOption({index:1});
  await page.locator('#sinv-grn').selectOption(grn.id);
  await expect(page.locator('#sinv-vendor')).toHaveValue(po.vendor_id);
  const invoiceNumber=`UAT-${info.project.name}-${Date.now()}`;
  await page.locator('#sinv-number').fill(invoiceNumber);
  await page.locator('#sinv-item').fill(item);
  await page.locator('#sinv-qty').fill('2');
  await page.locator('#sinv-price').fill('12000');
  const invoiceSaved=page.waitForResponse(r=>r.url().includes('action=enterprise-suite')&&r.request().method()==='POST'&&r.request().postData()?.includes('supplier-invoice-save'));
  await page.locator('#supplier-invoice-form button[type="submit"]').click();
  const invoiceResponse=await invoiceSaved,invoiceBody=await invoiceResponse.json();
  expect(invoiceResponse.status()).toBe(200);expect(invoiceBody.success).toBe(true);
  const invoice=invoiceBody.data.invoice;
  expect(invoice.status).toBe('draft');expect(Number(invoice.total_amount)).toBe(24000);
  await expect(page.locator('#sinv-list tr').filter({hasText:invoiceNumber})).toContainText('draft');
  page.once('dialog',dialog=>dialog.accept());
  const invoicePosted=page.waitForResponse(r=>r.url().includes('action=enterprise-suite')&&r.request().method()==='POST'&&r.request().postData()?.includes('supplier-invoice-post'));
  await page.locator('#sinv-list tr').filter({hasText:invoiceNumber}).getByRole('button',{name:'Post'}).click();
  const postedInvoiceResponse=await invoicePosted,postedInvoice=await postedInvoiceResponse.json();
  expect(postedInvoiceResponse.status()).toBe(200);expect(postedInvoice.success).toBe(true);
  expect(postedInvoice.data.invoice.status).toBe('posted');
  expect(postedInvoice.canonicalAccrualTransactionIds).toHaveLength(1);
  await expect(page.locator('#sinv-list tr').filter({hasText:invoiceNumber})).toContainText('posted');
  await page.reload();await expect(page.locator('#loading')).toBeHidden();await page.locator('[data-tab="ap"]').click();
  await expect(page.locator('#sinv-list tr').filter({hasText:invoiceNumber})).toContainText('posted');
  fs.writeFileSync(`artifacts/browser-pr-${info.project.name}.json`,JSON.stringify({test:'browser PR-to-PO-to-GRN-to-supplier-invoice lifecycle',pass:true,requestId:d.data.request.id,poId:po.id,grnId:grn.id,invoiceId:invoice.id,scope:'PR, PO, GRN and invoice accrual UI lifecycle in fixture; no AP payment or linked physical stock mutation claimed'}));
});

test('Enterprise CRM: consent, loyalty points and voucher depend on each other and persist',async({page},info)=>{
  await page.goto('/enterprise-suite.html');
  await expect(page.locator('#loading')).toBeHidden();

  // The guest profile is a PRECONDITION created through the API, because no UI
  // creates one. It must be seeded from inside the page: `issueSessionTokens()`
  // revokes every existing session for the same staff AND device, so a second
  // login on this device would invalidate the token the suite is already
  // running with and turn every later request into a 401.
  const stamp=`UATCRM-${info.project.name}-${Date.now()}`;
  const guestId=`uat_crm_${info.project.name}_${Date.now()}`;
  const operationId=`uat-crm-seed-${info.project.name}-${Date.now()}`;
  const seeded=await page.evaluate(async payload=>{
    const response=await fetch('/api.php?action=operations-center',{method:'POST',
      headers:{'Content-Type':'application/json','Accept':'application/json',
        'Authorization':'Bearer '+sessionStorage.getItem('hotel_session_token'),
        'X-Device-ID':'uat-browser','X-App-Version':'V137','X-Tamasya-Operation-ID':payload.operationId},
      body:JSON.stringify(payload.body)});
    return {status:response.status,body:await response.json().catch(()=>null)};
  },{operationId,body:{command:'guest-profile-save',operationId,id:guestId,name:`${stamp} Guest`,email:`${stamp.toLowerCase()}@example.invalid`}});
  expect(seeded.status).toBe(200);
  expect(seeded.body?.success).toBe(true);

  await page.locator('[data-tab="crm"]').click();
  await expect(page.locator('#tab-crm')).toBeVisible();

  // Search, then pick the exact seeded row. The result table is rendered by the
  // server from guest-search, so the row existing proves the query worked.
  await page.locator('#guest-q').fill(`${stamp} Guest`);
  const searched=page.waitForResponse(r=>r.url().includes('action=enterprise-suite')&&r.url().includes('command=guest-search'));
  await page.locator('#guest-search').click();
  const searchResponse=await searched;
  const searchBody=await searchResponse.json().catch(()=>null);
  fs.writeFileSync(`artifacts/browser-crm-diagnostic-${info.project.name}.json`,JSON.stringify({stage:'guest-search',httpStatus:searchResponse.status(),success:searchBody?.success===true,error:searchBody?String(searchBody.error??'').slice(0,200):null,rows:Array.isArray(searchBody?.data)?searchBody.data.length:null,query:searchResponse.url().split('&').filter(x=>x.startsWith('q=')).join('')}));
  expect(searchResponse.status()).toBe(200);
  const row=page.locator('#guest-results tr').filter({hasText:`${stamp} Guest`});
  await expect(row).toHaveCount(1);

  const selectGuest=async()=>{
    const detail=page.waitForResponse(r=>r.url().includes('action=enterprise-suite')&&r.url().includes('command=loyalty-detail'));
    const pick=row.getByRole('button',{name:'Pilih'});
    if(info.project.name==='mobile')await pick.tap({timeout:15000});else await pick.click({timeout:15000});
    expect((await detail).status()).toBe(200);
    // Selecting a guest is the only thing that populates the three downstream forms.
    await expect(page.locator('#consent-guest')).toHaveValue(guestId);
    await expect(page.locator('#points-guest')).toHaveValue(guestId);
    await expect(page.locator('#voucher-guest')).toHaveValue(guestId);
  };
  await selectGuest();
  await expect(page.locator('#loyalty-detail')).toContainText('Belum menjadi member');
  await expect(page.locator('#loyalty-detail')).toContainText('Poin: 0');

  const consentSave=async(status)=>{
    await page.locator('#consent-type').selectOption('loyalty_program');
    await page.locator('#consent-status').selectOption(status);
    await page.locator('#consent-evidence').fill(`${stamp}-${status}`);
    const posted=page.waitForResponse(r=>r.url().includes('action=enterprise-suite')&&r.request().method()==='POST'&&r.request().postData()?.includes('consent-save'));
    await page.locator('#consent-form button[type="submit"]').click();
    const response=await posted;
    expect(response.status()).toBe(200);
    expect((await response.json()).success).toBe(true);
    await expect(page.locator('#toast')).toContainText('Consent disimpan');
    await expect(page.locator('#loading')).toBeHidden();
  };
  const pointsSave=async(points,reason,accepted)=>{
    await page.locator('#points-value').fill(String(points));
    await page.locator('#points-reason').fill(reason);
    const posted=page.waitForResponse(r=>r.url().includes('action=enterprise-suite')&&r.request().method()==='POST'&&r.request().postData()?.includes('loyalty-adjust'));
    await page.locator('#points-form button[type="submit"]').click();
    const response=await posted,body=await response.json();
    if(accepted){expect(response.status()).toBe(200);expect(body.success).toBe(true);}
    else{expect(body.success).toBe(false);expect(String(body.error)).toContain('negatif');}
    await expect(page.locator('#loading')).toBeHidden();
  };
  const issueVoucher=async(value,accepted)=>{
    await page.locator('#voucher-type').selectOption('amount');
    await page.locator('#voucher-value').fill(String(value));
    await page.locator('#voucher-min').fill('0');
    await page.locator('#voucher-notes').fill(stamp);
    const today=new Date().toISOString().slice(0,10);
    await page.locator('#voucher-from').fill(today);
    await page.locator('#voucher-until').fill(today);
    const posted=page.waitForResponse(r=>r.url().includes('action=enterprise-suite')&&r.request().method()==='POST'&&r.request().postData()?.includes('loyalty-voucher-issue'));
    await page.locator('#voucher-form button[type="submit"]').click();
    const response=await posted,body=await response.json();
    if(accepted){expect(response.status()).toBe(200);expect(body.success).toBe(true);}
    else{expect(body.success).toBe(false);expect(String(body.error)).toContain('Consent loyalty_program aktif diperlukan');}
    await expect(page.locator('#loading')).toBeHidden();
    return body;
  };

  // With no loyalty_program consent yet, voucher issue must be refused. This is
  // the cross-control rule the UI has no other way to express.
  await issueVoucher(75000,false);
  await expect(page.locator('#voucher-list')).toContainText('Belum ada data');

  await consentSave('granted');
  await expect(page.locator('#loyalty-detail')).toContainText('Consent records: 1');

  // Points: a positive adjustment creates the account and moves the balance.
  await pointsSave(250,`${stamp} earn`,true);
  await expect(page.locator('#loyalty-detail')).toContainText('Poin: 250');
  await expect(page.locator('#loyalty-detail')).not.toContainText('Belum menjadi member');
  // Over-withdrawal must be refused by the server and must not move the balance.
  await pointsSave(-250.01,`${stamp} overdraw`,false);
  await expect(page.locator('#loyalty-detail')).toContainText('Poin: 250');

  const issued=await issueVoucher(75000,true);
  expect(issued.data.status).toBe('issued');
  expect(Number(issued.data.value_amount)).toBe(75000);
  await expect(page.locator('#voucher-list tr').filter({hasText:issued.data.voucher_code})).toContainText('issued');

  // Consent is append-only: revoking adds a second record rather than editing one.
  await consentSave('revoked');
  await expect(page.locator('#loyalty-detail')).toContainText('Consent records: 2');
  // Revocation must immediately block a further voucher, proving the guard is
  // read at issue time and not cached from the earlier grant.
  await issueVoucher(75000,false);

  // Reload the whole page and re-select: the state must come back from the server.
  await page.reload();
  await expect(page.locator('#loading')).toBeHidden();
  await page.locator('[data-tab="crm"]').click();
  await page.locator('#guest-q').fill(`${stamp} Guest`);
  const reloadedSearch=page.waitForResponse(r=>r.url().includes('action=enterprise-suite')&&r.url().includes('command=guest-search'));
  await page.locator('#guest-search').click();
  await reloadedSearch;
  const reloadDetail=page.waitForResponse(r=>r.url().includes('action=enterprise-suite')&&r.url().includes('command=loyalty-detail'));
  const reloadedPick=page.locator('#guest-results tr').filter({hasText:`${stamp} Guest`}).getByRole('button',{name:'Pilih'});
  if(info.project.name==='mobile')await reloadedPick.tap({timeout:15000});else await reloadedPick.click({timeout:15000});
  await reloadDetail;
  await expect(page.locator('#loyalty-detail')).toContainText('Poin: 250');
  await expect(page.locator('#loyalty-detail')).toContainText('Consent records: 2');
  await expect(page.locator('#voucher-list tr').filter({hasText:issued.data.voucher_code})).toContainText('issued');
  fs.writeFileSync(`artifacts/browser-crm-${info.project.name}.json`,JSON.stringify({test:'CRM consent gating, loyalty points exact balance and voucher persistence across reload',pass:true,guestId,consentRecords:2,pointsBalance:'250',voucherCode:issued.data.voucher_code,deniedWithoutConsent:true,deniedAfterRevocation:true,deniedOverdraft:true,scope:'Guest profile seeded through the API as a precondition. UI consent append-only, negative-balance rejection, consent-gated voucher issue and persisted reload verified. Voucher redemption, campaign send, role denial and Telegram not claimed'}));
});

test('POS: every tab, product draft cancel, creation, search and cart clear',async({page},info)=>{
  const errors=[];page.on('pageerror',e=>errors.push(e.message));
  await page.goto('/pos.html');await expect(page.locator('#product-grid [data-product]').first()).toBeVisible();
  for(const view of ['cashier','products','stock','sales','deliveries']){
    await page.locator(`[data-view="${view}"]`).click();
    await expect(page.locator(`#view-${view}`)).toBeVisible();
  }
  await page.locator('[data-view="products"]').click();
  await page.locator('#add-product-btn').click();await expect(page.locator('#product-dialog')).toBeVisible();
  await page.locator('#cancel-product-dialog').click();await expect(page.locator('#product-dialog')).toBeHidden();
  await page.locator('#add-product-btn').click();
  const sku='UAT-'+info.project.name+'-'+Date.now(),name='UAT browser product '+sku;
  await page.locator('#product-sku').fill(sku);await page.locator('#product-name').fill(name);
  await page.locator('#product-cost').fill('1000');await page.locator('#product-price').fill('2000');
  await page.locator('#product-initial-stock').fill('5');
  const saved=page.waitForResponse(r=>r.url().includes('action=pos-product-save')&&r.request().method()==='POST');
  await page.locator('#save-product').click();const response=await saved;
  expect(response.status()).toBe(200);expect((await response.json()).success).toBe(true);
  await expect(page.locator('#product-dialog')).toBeHidden();
  await expect(page.locator('#products-table')).toContainText(sku);
  await page.reload();await page.locator('[data-view="cashier"]').click();
  await page.locator('#product-search').fill(sku);
  const product=page.locator('#product-grid [data-product]');await expect(product).toHaveCount(1);await expect(product).toContainText(name);
  await expect(page.locator('#checkout-btn')).toBeDisabled();await product.click();await expect(page.locator('#checkout-btn')).toBeEnabled();
  await expect(page.locator('#cart-list')).toContainText(name);await page.locator('#clear-cart').click();await expect(page.locator('#checkout-btn')).toBeDisabled();
  expect(errors).toEqual([]);
  fs.writeFileSync(`artifacts/browser-pos-${info.project.name}.json`,JSON.stringify({test:'POS navigation, cancel, persist product, search and clear cart',pass:true,sku,scope:'No completed sale, refund or device printing claimed'}));
});
test('POS cash sale and void: receipt, history and stock reversal persist',async({page},info)=>{
  await page.goto('/pos.html');
  await expect(page.locator('#product-grid [data-product]').first()).toBeVisible();
  await page.locator('[data-view="products"]').click();
  await page.locator('#add-product-btn').click();
  const sku=`UAT-SALE-${info.project.name}-${Date.now()}`;
  const name=`UAT sale product ${sku}`;
  await page.locator('#product-sku').fill(sku);
  await page.locator('#product-name').fill(name);
  await page.locator('#product-cost').fill('1000');
  await page.locator('#product-price').fill('2000');
  await page.locator('#product-initial-stock').fill('5');
  const productSaved=page.waitForResponse(r=>r.url().includes('action=pos-product-save')&&r.request().method()==='POST');
  await page.locator('#save-product').click();
  expect((await productSaved).status()).toBe(200);
  await expect(page.locator('#product-dialog')).toBeHidden();
  await page.locator('[data-view="cashier"]').click();
  await page.locator('#product-search').fill(sku);
  const product=page.locator('#product-grid [data-product]');
  await expect(product).toHaveCount(1);
  await product.click();
  await page.locator('#payment-method').selectOption('cash');
  page.on('dialog',dialog=>dialog.accept(dialog.type()==='prompt'?'UAT void reversal':''));
  const sold=page.waitForResponse(r=>r.url().includes('action=pos-sale-create')&&r.request().method()==='POST');
  await page.locator('#checkout-btn').click();
  const saleResponse=await sold;
  expect(saleResponse.status()).toBe(200);
  const saleBody=await saleResponse.json();
  expect(saleBody.success).toBe(true);
  expect(saleBody.sale.status).toBe('posted');
  expect(saleBody.sale.paymentMethod).toBe('cash');
  expect(Number(saleBody.sale.grossAmount)).toBe(2000);
  const receipt=saleBody.sale.receiptNumber;
  await expect(page.locator('#receipt-dialog')).toBeVisible();
  await expect(page.locator('#receipt-content')).toContainText(receipt);
  await page.locator('#close-receipt').click();
  await page.locator('[data-view="products"]').click();
  const productRow=page.locator('#products-table tr').filter({hasText:sku});
  await expect(productRow.locator('td').nth(3)).toContainText('1.000');
  await expect(productRow.locator('td').nth(4)).toContainText('4 pcs');
  await page.locator('[data-view="sales"]').click();
  const listed=page.waitForResponse(r=>r.url().includes('action=pos-sales'));
  await page.locator('#load-sales').click();
  expect((await listed).status()).toBe(200);
  const saleRow=page.locator('#sales-table tr').filter({hasText:receipt});
  await expect(saleRow).toContainText('posted');
  const voided=page.waitForResponse(r=>r.url().includes('action=pos-sale-void')&&r.request().method()==='POST');
  await saleRow.getByRole('button',{name:'Void'}).click();
  const voidResponse=await voided;
  expect(voidResponse.status()).toBe(200);
  expect((await voidResponse.json()).success).toBe(true);
  await expect(saleRow).toContainText('voided');
  await page.reload();
  await page.locator('[data-view="products"]').click();
  await expect(page.locator('#products-table tr').filter({hasText:sku}).locator('td').nth(3)).toContainText('1.000');
  await expect(page.locator('#products-table tr').filter({hasText:sku}).locator('td').nth(4)).toContainText('5 pcs');
  await page.locator('[data-view="sales"]').click();
  const reloaded=page.waitForResponse(r=>r.url().includes('action=pos-sales'));
  await page.locator('#load-sales').click();
  expect((await reloaded).status()).toBe(200);
  await expect(page.locator('#sales-table tr').filter({hasText:receipt})).toContainText('voided');
  fs.writeFileSync(`artifacts/browser-pos-sale-${info.project.name}.json`,JSON.stringify({test:'POS cash sale, receipt, history and void stock reversal',pass:true,scope:'No external payment, physical printer or room delivery claimed'}));
});
test('POS stock adjustment: add, subtract and persisted reload',async({page},info)=>{
  await page.goto('/pos.html');
  await expect(page.locator('#product-grid [data-product]').first()).toBeVisible();
  await page.locator('[data-view="products"]').click();
  await page.locator('#add-product-btn').click();
  const sku=`UAT-STOCK-${info.project.name}-${Date.now()}`;
  await page.locator('#product-sku').fill(sku);
  await page.locator('#product-name').fill(`UAT stock product ${sku}`);
  await page.locator('#product-cost').fill('500');
  await page.locator('#product-price').fill('1000');
  await page.locator('#product-initial-stock').fill('5');
  const created=page.waitForResponse(r=>r.url().includes('action=pos-product-save')&&r.request().method()==='POST');
  await page.locator('#save-product').click();
  expect((await created).status()).toBe(200);
  await expect(page.locator('#product-dialog')).toBeHidden();
  await page.locator('[data-view="stock"]').click();
  const adjust=async(delta,reason,expected)=>{
    const option=page.locator('#stock-product option').filter({hasText:sku});
    const productId=await option.getAttribute('value');
    expect(productId).toBeTruthy();
    await page.locator('#stock-product').selectOption(productId);
    await page.locator('#stock-delta').fill(String(delta));
    await page.locator('#stock-reason').fill(reason);
    const posted=page.waitForResponse(r=>r.url().includes('action=pos-stock-adjust')&&r.request().method()==='POST');
    await page.locator('#stock-form button[type="submit"]').click();
    const response=await posted;
    expect(response.status()).toBe(200);
    expect((await response.json()).success).toBe(true);
    await page.locator('[data-view="products"]').click();
    await expect(page.locator('#products-table tr').filter({hasText:sku}).locator('td').nth(4)).toContainText(`${expected} pcs`);
    await page.locator('[data-view="stock"]').click();
  };
  await adjust(2,'UAT stock addition',7);
  await adjust(-1,'UAT stock reduction',6);
  await page.reload();
  await page.locator('[data-view="products"]').click();
  await expect(page.locator('#products-table tr').filter({hasText:sku}).locator('td').nth(4)).toContainText('6 pcs');
  fs.writeFileSync(`artifacts/browser-pos-stock-${info.project.name}.json`,JSON.stringify({test:'POS positive/negative stock adjustment and persisted balance',pass:true,scope:'Stock audit and permission matrix not yet claimed as browser-tested'}));
});
test('POS categories: create, reset, edit, toggle and persisted reload',async({page},info)=>{
  await page.goto('/pos.html');
  await expect(page.locator('#product-grid [data-product]').first()).toBeVisible();
  await page.locator('[data-view="products"]').click();
  await page.locator('#manage-categories-btn').click();
  await expect(page.locator('#category-dialog')).toBeVisible();
  const name=`UAT category ${info.project.name} ${Date.now()}`;
  const updated=`${name} updated`;
  const save=async()=>{
    const posted=page.waitForResponse(r=>r.url().includes('action=pos-category-save')&&r.request().method()==='POST');
    await page.locator('#save-category').click();
    const response=await posted;
    expect(response.status()).toBe(200);
    expect((await response.json()).success).toBe(true);
  };
  await page.locator('#category-name').fill(name);
  await save();
  await expect(page.locator('#categories-table tr').filter({hasText:name})).toHaveCount(1);
  await page.reload();
  await page.locator('[data-view="products"]').click();
  await page.locator('#manage-categories-btn').click();
  const row=page.locator('#categories-table tr').filter({hasText:name});
  await expect(row).toHaveCount(1);
  await row.getByRole('button',{name:'Edit'}).click();
  await expect(page.locator('#category-name')).toHaveValue(name);
  await page.locator('#reset-category-form').click();
  await expect(page.locator('#category-name')).toHaveValue('');
  await row.getByRole('button',{name:'Edit'}).click();
  await page.locator('#category-name').fill(updated);
  await save();
  const updatedRow=page.locator('#categories-table tr').filter({hasText:updated});
  await expect(updatedRow).toHaveCount(1);
  page.on('dialog',dialog=>dialog.accept());
  const disabled=page.waitForResponse(r=>r.url().includes('action=pos-category-save')&&r.request().method()==='POST');
  await updatedRow.getByRole('button',{name:'Nonaktifkan'}).click();
  expect((await disabled).status()).toBe(200);
  await expect(updatedRow.locator('td').nth(3)).toHaveText('Nonaktif');
  const enabled=page.waitForResponse(r=>r.url().includes('action=pos-category-save')&&r.request().method()==='POST');
  await updatedRow.getByRole('button',{name:'Aktifkan'}).click();
  expect((await enabled).status()).toBe(200);
  await expect(updatedRow.locator('td').nth(3)).toHaveText('Aktif');
  await page.locator('#cancel-category-dialog').click();
  await expect(page.locator('#category-dialog')).toBeHidden();
  await page.reload();
  await page.locator('[data-view="products"]').click();
  await page.locator('#manage-categories-btn').click();
  await expect(page.locator('#categories-table tr').filter({hasText:updated}).locator('td').nth(3)).toHaveText('Aktif');
  fs.writeFileSync(`artifacts/browser-pos-category-${info.project.name}.json`,JSON.stringify({test:'POS category lifecycle through UI and persisted reload',pass:true,scope:'Category with no products; delete and category-in-use guard not claimed'}));
});
test('PMS interactive login: credentials, session and reload',async({browser},info)=>{
  const mobile=info.project.name==='mobile';
  const context=await browser.newContext({viewport:mobile?{width:390,height:844}:{width:1440,height:1000},
    isMobile:mobile,hasTouch:mobile,serviceWorkers:'block'});
  try{
    await context.route('**/*',route=>{
      const url=new URL(route.request().url());
      return ['127.0.0.1','localhost'].includes(url.hostname)?route.continue():route.abort();
    });
    const loginPage=await context.newPage();
    await loginPage.goto(base+'/index.html');
    const username=loginPage.getByPlaceholder('Contoh: admin, reps, finance, manager');
    const password=loginPage.getByPlaceholder('Masukkan password Anda...');
    const submit=loginPage.getByRole('button',{name:'Masuk ke Konsol'});
    await expect(username).toBeVisible();
    await expect(password).toBeVisible();
    await username.fill(env.APP_BOOTSTRAP_ADMIN_USERNAME);
    await password.fill(env.APP_BOOTSTRAP_ADMIN_PASSWORD);
    const completed=loginPage.waitForResponse(r=>r.url().includes('action=login')||r.url().endsWith('/api/login'));
    await submit.click();
    const response=await completed;
    expect(response.status()).toBe(200);
    expect((await response.json()).token).toBeTruthy();
    await expect.poll(()=>loginPage.evaluate(()=>Boolean(sessionStorage.getItem('hotel_session_token')))).toBe(true);
    await expect(submit).toBeHidden();
    await loginPage.reload();
    await expect(submit).toBeHidden();
    await expect.poll(()=>loginPage.evaluate(()=>Boolean(sessionStorage.getItem('hotel_session_token')))).toBe(true);
    fs.writeFileSync(`artifacts/browser-login-${info.project.name}.json`,JSON.stringify({test:'interactive PMS login and session reload',pass:true,scope:'Positive admin login only; 2FA, lockout and password recovery not claimed'}));
  }finally{
    await context.close();
  }
});
