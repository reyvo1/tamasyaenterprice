from growth_client import request,base
from pathlib import Path
import json,secrets,subprocess,datetime,urllib.parse
from runtime_tools import mysql_binary
b=Path(__file__).resolve().parent;e=json.loads((base/'environment.json').read_text(encoding='utf-8'));db=e['APP_EXPECTED_DB_NAME'];assert db.startswith('tamasya_growth_test_')
args=[mysql_binary(),'--defaults-file='+str(b/'client.ini'),'--batch','--skip-column-names',db]
def sql(q):
 r=subprocess.run(args,input=q,capture_output=True,text=True,encoding='utf-8');r.check_returncode();return r.stdout.strip()
assert sql('SELECT @@port')=='23384'
results=[];prefix='c'+secrets.token_hex(5);today=datetime.datetime.now(datetime.timezone(datetime.timedelta(hours=8))).date().isoformat()
def check(name,ok,detail=None):
 results.append({'name':name,'pass':bool(ok),'detail':detail});(b/'growth-crm-results.json').write_text(json.dumps(results,indent=2),encoding='utf-8');print('PASS' if ok else 'FAIL',name,flush=True)
 if not ok:raise AssertionError(str(detail))
def post(command,data=None,action='enterprise-suite',expected=True,op=None):
 payload={'command':command,**(data or {}),'operationId':op or prefix+'_'+secrets.token_hex(7)};s,d=request(action,'POST',payload,payload['operationId']);check(command+' '+('accepted' if expected else 'rejected'),(s==200 and d.get('success') is True)==expected,{'status':s,'error':d.get('error',d.get('message'))});return d
before=sql('SELECT CONCAT(COUNT(*),"|",SUM(amount)) FROM transactions')
guest=prefix+'_guest';post('guest-profile-save',{'id':guest,'name':'CRM integration guest','email':prefix+'@example.invalid'},'operations-center')
booking=sql("SELECT b.id FROM bookings b WHERE b.status='completed' AND b.totalAmount>0 AND NOT EXISTS(SELECT 1 FROM growth_guest_booking_links l WHERE l.booking_id=b.id) ORDER BY b.id LIMIT 1");assert booking
post('guest-booking-link',{'guestProfileId':guest,'bookingId':booking},expected=False)
post('guest-booking-link',{'guestProfileId':guest,'bookingId':booking,'manualConfirmed':True})
award=post('loyalty-award-booking',{'bookingId':booking});points=float(award['data']['account']['points_balance'])
post('loyalty-award-booking',{'bookingId':booking});check('Stay award cannot duplicate points',float(sql("SELECT points_balance FROM growth_loyalty_accounts WHERE guest_profile_id='"+guest+"'"))==points)
post('loyalty-adjust',{'guestProfileId':guest,'points':-(points+0.01),'reason':'Overdraw guard fixture'},expected=False)
post('loyalty-adjust',{'guestProfileId':guest,'points':25,'reason':'Approved integration adjustment'})
post('loyalty-voucher-issue',{'guestProfileId':guest,'valueType':'benefit','notes':'Local fixture only'},expected=False)
post('consent-save',{'guestProfileId':guest,'consentType':'loyalty_program','status':'granted','evidenceReference':'fixture-consent'})
voucher=post('loyalty-voucher-issue',{'guestProfileId':guest,'valueType':'benefit','notes':'Local fixture only'})['data']['id']
post('loyalty-voucher-redeem',{'voucherId':voucher,'bookingId':booking,'reference':'Approved fixture benefit'})
other=sql("SELECT id FROM bookings WHERE id<>'"+booking+"' LIMIT 1")
post('loyalty-voucher-redeem',{'voucherId':voucher,'bookingId':other,'reference':'Wrong booking fixture'},expected=False)
post('consent-save',{'guestProfileId':guest,'consentType':'loyalty_program','status':'revoked','evidenceReference':'fixture-revocation'})
post('loyalty-voucher-issue',{'guestProfileId':guest,'valueType':'benefit'},expected=False)
segment=post('crm-segment-save',{'code':prefix,'name':'Fixture segment','condition':{'email_required':True}})['data']['id']
campaign=post('crm-campaign-save',{'name':'Fixture campaign','segmentId':segment,'channel':'email','subject':'Local fixture','messageTemplate':'Fixture only'})['data']['id']
post('crm-campaign-snapshot',{'id':campaign},expected=False);post('crm-campaign-approve',{'id':campaign})
post('crm-campaign-snapshot',{'id':campaign});check('No marketing without consent',sql("SELECT COUNT(*) FROM growth_crm_campaign_recipients WHERE campaign_id='"+campaign+"' AND guest_profile_id='"+guest+"'")=='0')
post('consent-save',{'guestProfileId':guest,'consentType':'email_marketing','status':'granted','evidenceReference':'fixture-email-consent'})
post('crm-campaign-snapshot',{'id':campaign});check('Explicit consent includes fixture recipient',sql("SELECT COUNT(*) FROM growth_crm_campaign_recipients WHERE campaign_id='"+campaign+"' AND guest_profile_id='"+guest+"'")=='1')
post('consent-save',{'guestProfileId':guest,'consentType':'email_marketing','status':'revoked'})
post('crm-campaign-snapshot',{'id':campaign});check('Revocation removes pending fixture recipient',sql("SELECT COUNT(*) FROM growth_crm_campaign_recipients WHERE campaign_id='"+campaign+"' AND guest_profile_id='"+guest+"'")=='0')
post('crm-campaign-send-batch',{'id':campaign},expected=False)
post('provider-adapter-save',{'adapterType':'payment','providerCode':prefix,'mode':'sandbox','config':{},'credentialReference':'plaintext-secret'},expected=False)
adapter=post('provider-adapter-save',{'adapterType':'payment','providerCode':prefix,'mode':'sandbox','config':{},'credentialReference':'env:TAMASYA_TEST_UNUSED','active':False})['data']['id']
s,d=request('enterprise-suite&command=provider-adapter-self-test&id='+adapter);check('Provider metadata never claims financial mutation',s==200 and d['data']['externalMutationEnabled'] is False and d['data']['metadataReady'] is False)
check('CRM actions preserve canonical money',before==sql('SELECT CONCAT(COUNT(*),"|",SUM(amount)) FROM transactions'))
print('CRM assertions passed:',len(results))
