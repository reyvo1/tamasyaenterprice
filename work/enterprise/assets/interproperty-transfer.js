(()=>{'use strict';
const $=id=>document.getElementById(id),esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let storageKey='',rows=[],next=null,busy=false,identity=null;
const token=()=>sessionStorage.getItem('hotel_session_token')||'';
function device(){let id=localStorage.getItem('hotel_device_id');if(!id){id='device_'+crypto.randomUUID();localStorage.setItem('hotel_device_id',id);}return id;}
function status(message){$('status').textContent=message;}
function pending(){if(!storageKey)return null;try{return JSON.parse(localStorage.getItem(storageKey)||'null');}catch{throw Error('Permintaan tersimpan tidak dapat dibaca; periksa histori sebelum mencatat ulang.');}}
function controls(){const retained=!!pending();$('pending').hidden=!retained;for(const element of document.querySelectorAll('form button,form input,form select'))element.disabled=busy||retained;$('retry').disabled=busy;$('refresh').disabled=busy;}
async function api(body=null,offset=0){
 const headers={Accept:'application/json',Authorization:'Bearer '+token(),'X-Device-ID':device()};
 const hotelScope=sessionStorage.getItem('hotel_offline_hotel_scope');if(hotelScope)headers['X-Tamasya-Hotel-Scope']=hotelScope;
 if(body){headers['Content-Type']='application/json';headers['X-Tamasya-Operation-ID']=body.operationId;}
 const r=await fetch('./api.php?action=interproperty-transfer&offset='+offset,{method:body?'POST':'GET',headers,body:body?JSON.stringify(body):undefined,cache:'no-store',credentials:'same-origin'});
 const d=await r.json();if(!r.ok||d.success!==true){const error=Error(d.error||d.message||'Permintaan belum berhasil');error.httpStatus=r.status;throw error;}return d.data;
}
function download(document,id){const url=URL.createObjectURL(new Blob([JSON.stringify(document,null,2)],{type:'application/json'})),a=document.createElement('a');a.href=url;a.download=id+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);}
function render(){
 const labels={awaiting_receipt:'Menunggu bukti penerima',received:'Dana masuk dicatat',reconciled:'Bukti kedua pihak cocok'};
 $('history').innerHTML='<table><thead><tr><th>Transfer / referensi</th><th>Properti pasangan</th><th>Nominal</th><th>Status</th><th>Bukti</th></tr></thead><tbody>'+rows.map((r,i)=>`<tr><td>${esc(r.id)}<br>${esc(r.reference)}</td><td>${esc(r.peer_property_id)} · ${r.direction==='out'?'Keluar':'Masuk'}</td><td>${esc(r.currency)} ${esc(r.amount)}</td><td>${esc(labels[r.status]||r.status)}</td><td><button class="btn tiny" data-order="${i}">Dokumen sumber</button>${r.receipt?` <button class="btn tiny" data-receipt="${i}">Bukti penerimaan</button>`:''}</td></tr>`).join('')+'</tbody></table>';
 for(const button of document.querySelectorAll('[data-order]'))button.onclick=()=>{const r=rows[Number(button.dataset.order)];download(r.order,r.id+'-sumber');};
 for(const button of document.querySelectorAll('[data-receipt]'))button.onclick=()=>{const r=rows[Number(button.dataset.receipt)];download(r.receipt,r.id+'-penerimaan');};$('more').hidden=next===null;
}
async function load(append=false){const d=await api(null,append?next:0);$('workspace').hidden=!d.enabled;if(!d.enabled){status('Transfer antarproperti belum diaktifkan untuk hotel ini.');return;}
 identity=d.identity;if(!d.actorId)throw Error('Identitas petugas belum tersedia.');storageKey='tamasya_transfer_pending:'+identity.companyId+':'+identity.propertyId+':'+d.actorId;
 if(!append){$('peer').innerHTML=d.peers.map(x=>`<option value="${esc(x)}">${esc(x)}</option>`).join('');const options=d.bankAccounts.map(x=>`<option value="${esc(x.id)}">${esc(x.name)}</option>`).join('');$('source-account').innerHTML=options;$('destination-account').innerHTML=options;$('currency').textContent=identity.currency;}
 rows=append?rows.concat(d.rows):d.rows;next=d.nextOffset;
 const saved=pending();let recovered=false;if(saved){recovered=rows.some(r=>{
   if(saved.command==='create')return r.direction==='out'&&r.peer_property_id===saved.destinationPropertyId&&r.reference===saved.reference&&r.bank_account_id===saved.bankAccountId&&Math.round(Number(r.amount)*100)===Math.round(Number(saved.amount)*100);
   if(saved.command==='receive')return r.direction==='in'&&r.order?.signature===saved.document?.signature&&r.reference===saved.reference&&r.bank_account_id===saved.bankAccountId;
   return saved.command==='reconcile'&&r.status==='reconciled'&&r.receipt?.signature===saved.document?.signature;
 });if(recovered)localStorage.removeItem(storageKey);}
 render();controls();status(recovered?'Permintaan tersimpan sudah ditemukan pada histori server.':identity.propertyName+' · '+identity.propertyId);
}
async function submit(body){if(busy)return;busy=true;try{if(!storageKey)throw Error('Identitas properti belum tersedia.');if(body){if(pending())throw Error('Selesaikan permintaan tersimpan terlebih dahulu.');localStorage.setItem(storageKey,JSON.stringify({...body,operationId:'ip-ui-'+crypto.randomUUID()}));}const saved=pending();if(!saved)throw Error('Tidak ada permintaan tersimpan.');controls();const row=await api(saved);localStorage.removeItem(storageKey);await load();status('Tersimpan: '+row.id+' — '+row.status);}
 catch(error){if(error.httpStatus===422||error.httpStatus===400){localStorage.removeItem(storageKey);}status(error.message);}finally{busy=false;controls();}}
 $('outgoing').onsubmit=event=>{event.preventDefault();submit({command:'create',destinationPropertyId:$('peer').value,bankAccountId:$('source-account').value,amount:$('amount').value,reference:$('source-reference').value,confirmation:$('sent-confirm').checked?'DANA SUDAH DIKIRIM':''});};
 $('incoming').onsubmit=async event=>{event.preventDefault();try{const file=$('document-file').files[0];if(!file||file.size>65536)throw Error('Pilih dokumen JSON maksimal 64 KB.');const document=JSON.parse(await file.text()),command=$('import-kind').value;await submit({command,document,bankAccountId:$('destination-account').value,reference:$('destination-reference').value,confirmation:$('received-confirm').checked?'DANA SUDAH DITERIMA':''});}catch(error){status(error.message);}};
 $('import-kind').onchange=()=>{$('receipt-fields').hidden=$('import-kind').value==='reconcile';};$('retry').onclick=()=>submit(null);$('refresh').onclick=()=>load().catch(e=>status(e.message));$('more').onclick=()=>load(true).catch(e=>status(e.message));
 if(!token()){location.href='./login';return;}load().catch(error=>status(error.message));
})();
