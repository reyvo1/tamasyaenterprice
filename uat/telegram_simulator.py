"""Exercise actual simulator routes with binding and spoofed-role checks."""
from pathlib import Path
import json,os,secrets,subprocess,urllib.request,urllib.error
root=Path(__file__).resolve().parents[1];run=Path(os.environ['TAMASYA_UAT_RUN']);g=Path(os.environ['TAMASYA_UAT_FIXTURE'])
e=json.loads((g/'environment.json').read_text());db=e['APP_EXPECTED_DB_NAME'];assert db.startswith('tamasya_growth_test_')
results=[];token=None
def check(name,ok):
    results.append({'name':name,'pass':bool(ok)})
    (root/'artifacts/telegram-simulator-results.json').write_text(json.dumps(results,indent=2))
    assert ok,name
def api(action,data,auth=True):
    headers={'Origin':'http://127.0.0.1:28189','X-Device-ID':'uat-telegram','Content-Type':'application/json','X-Tamasya-Operation-ID':'uat_'+secrets.token_hex(12)}
    if auth and token:headers['Authorization']='Bearer '+token
    req=urllib.request.Request('http://127.0.0.1:28189/api.php?action='+action,headers=headers,data=json.dumps(data).encode())
    try:r=urllib.request.urlopen(req,timeout=90)
    except urllib.error.HTTPError as error:r=error
    return r.status,json.load(r)
s,d=api('login',{'username':e['APP_BOOTSTRAP_ADMIN_USERNAME'],'password':e['APP_BOOTSTRAP_ADMIN_PASSWORD']},False)
check('Admin fixture login',s==200 and bool(d.get('token')));token=d['token']
s,d=api('telegram-bot',{'text':'/menu','chatId':900000001,'role':'admin'})
check('Browser-supplied role cannot bind unknown Telegram identity',s==200 and d.get('success') is True and d.get('simulationIdentity',{}).get('bound') is False)
sql="UPDATE staff SET telegram_chat_id='900000002' WHERE username='"+e['APP_BOOTSTRAP_ADMIN_USERNAME']+"'"
subprocess.run(['mysql','--defaults-file='+str(run/'simulation/client.ini'),db],input=sql,capture_output=True,text=True,check=True)
for command in ['/start','/menu','/status_kamar','/laporan','/help']:
    s,d=api('telegram-bot',{'text':command,'chatId':900000002})
    check(command+' returns a bound admin reply',s==200 and d.get('success') is True and d.get('simulationIdentity',{}).get('bound') is True and bool(d.get('message',{}).get('text')))
for callback in ['main_menu','account_menu','account_profile','guest_ops_menu','field_ops_menu','cash_shift_menu',
    'housekeeping_menu','guest_identity_menu','booking_checkout_menu','booking_extend_menu',
    'booking_service_menu','booking_transfer_menu','leave_menu','leave_history','leave_team',
    'patrol_reports_menu','gsm:p:1','consistency_guard']:
    s,d=api('telegram-callback',{'callbackData':callback,'chatId':900000002,'messageId':'uat-menu'})
    check(callback+' renders authenticated callback reply',s==200 and d.get('success') is True and d.get('simulationIdentity',{}).get('bound') is True and bool(d.get('message',{}).get('text')))
s,d=api('telegram-bot',{'text':'/menu','chatId':900000002},False)
check('Anonymous caller cannot access admin simulator',s in (401,403))
args=['mysql','--defaults-file='+str(run/'simulation/client.ini'),'--batch','--skip-column-names',db]
def sql(query):return subprocess.run(args,input=query,capture_output=True,text=True,check=True).stdout.strip()
before=sql('SELECT COUNT(*),COALESCE(SUM(amount),0) FROM transactions')
for index,role in enumerate(['manager','finance','receptionist','koki','tukang_kebun','cleaning_service','keamanan','lain_lain']):
    identity='uat_tg_'+role;chat=str(900000100+index)
    # Fixture-only identities: reuse salted hash without exporting or printing it.
    sql("INSERT INTO staff(id,name,username,password,role,status,telegram_chat_id) SELECT '"+identity+"','UAT "+role+"','"+identity+"',password,'"+role+"','active','"+chat+"' FROM staff WHERE username='"+e['APP_BOOTSTRAP_ADMIN_USERNAME']+"'")
    s,d=api('telegram-bot',{'text':'/menu','chatId':int(chat),'role':'admin'})
    check(role+' menu resolves server-side binding, not forged admin role',s==200 and d.get('success') is True and d.get('simulationIdentity',{}).get('role')==role and bool(d.get('message',{}).get('text')))
    s,d=api('telegram-callback',{'callbackData':'account_profile','chatId':int(chat),'role':'admin','messageId':'uat-role'})
    check(role+' account callback retains real role',s==200 and d.get('success') is True and d.get('simulationIdentity',{}).get('role')==role)
check('Menu and profile navigation do not mutate financial ledger',sql('SELECT COUNT(*),COALESCE(SUM(amount),0) FROM transactions')==before)
print('Telegram simulator:',len(results),'checks; live not tested')
