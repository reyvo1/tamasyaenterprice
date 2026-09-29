from growth_client import request,base
from pathlib import Path
import json,secrets,subprocess
from runtime_tools import mysql_binary
b=Path(__file__).resolve().parent;e=json.loads((base/'environment.json').read_text(encoding='utf-8'));db=e['APP_EXPECTED_DB_NAME'];assert db.startswith('tamasya_growth_test_')
args=[mysql_binary(),'--defaults-file='+str(b/'client.ini'),'--batch','--skip-column-names',db]
def sql(q):
 r=subprocess.run(args,input=q,capture_output=True,text=True,encoding='utf-8');r.check_returncode();return r.stdout.strip()
assert sql('SELECT @@port')=='33384'
results=[];prefix='salary_'+secrets.token_hex(5)
def check(name,ok,detail=None):
 results.append({'name':name,'pass':bool(ok),'detail':detail});(b/'growth-payroll-results.json').write_text(json.dumps(results,indent=2),encoding='utf-8');print('PASS' if ok else 'FAIL',name,flush=True)
 if not ok:raise AssertionError(str(detail))
def post(name,data,action='salary-slips',expected=True,op=None):
 payload={**data,'operationId':op or prefix+'_'+secrets.token_hex(7)};s,d=request(action,'POST',payload,payload['operationId']);check(name,(s==200 and d.get('success') is True)==expected and (expected or s in [400,409,422,500]),{'status':s,'error':d.get('error',d.get('message'))});return d
if sql("SELECT COUNT(*) FROM shift_sessions WHERE status='open'")=='0':post('Open fixture shift',{'command':'shift-open','openingCash':100000,'shiftTime':'malam'},'operations-center')
if sql("SELECT COUNT(*) FROM categories WHERE system_key='payroll_expense' AND is_active=1")=='0':
 category=post('Create payroll category',{'name':'Fixture Payroll','type':'expense'},'categories')['categoryId']
 post('Bind payroll semantics',{'categoryId':category,'systemKey':'payroll_expense'},'categories-semantic-bind')
staff=sql("SELECT id FROM staff WHERE role='admin' AND status='active' LIMIT 1")
slip={'id':prefix,'staffId':staff,'period':prefix,'basicSalary':100000,'bonus':5000,'detailedAllowances':[{'name':'Transport','amount':10000}],'detailedDeductions':[{'name':'Adjustment','amount':2000}],'netSalary':113000,'status':'draft','sendTelegram':False}
post('Draft payroll',slip)
check('Draft never moves money',sql("SELECT COUNT(*) FROM transactions WHERE sourceEntityId='"+prefix+"'")=='0')
paid={**slip,'status':'paid','paymentMethod':'cash'}
post('Pay salary',paid);post('Repeat paid slip',paid)
check('Salary payment exactly once',sql("SELECT COUNT(*) FROM transactions WHERE sourceEntityId='"+prefix+"' AND transactionKind='salary_payment'")=='1')
check('Cash salary belongs to open shift',sql("SELECT COUNT(*) FROM transactions t JOIN shift_sessions s ON s.id=t.shiftSessionId WHERE t.sourceEntityId='"+prefix+"' AND s.status='open'")=='1')
post('Paid salary immutable even for one cent',{**paid,'basicSalary':100000.01,'netSalary':113000.01},expected=False)
post('Paid salary cannot become draft',slip,expected=False)
post('Malformed amount rejected',{**slip,'id':prefix+'_bad','basicSalary':'not-money'},expected=False)
post('Malformed component rejected',{**slip,'id':prefix+'_bad2','detailedAllowances':[{'name':'Invalid','amount':True}]},expected=False)
correction={'command':'correct','slipId':prefix,'reason':'Local correction fixture','confirmation':'KOREKSI GAJI','basicSalary':120000,'allowances':0,'deductions':0,'bonus':0,'netSalary':120000,'paymentMethod':'cash'}
count=sql('SELECT COUNT(*) FROM transactions')
post('Negative correction component rejected',{**correction,'basicSalary':-1000,'bonus':121000},'salary-payment-correction',False)
post('Correction total mismatch rejected',{**correction,'netSalary':120000.01},'salary-payment-correction',False)
check('Rejected corrections atomically preserve ledger',count==sql('SELECT COUNT(*) FROM transactions'))
op=prefix+'_correct';post('Correct salary atomically',correction,'salary-payment-correction',op=op);post('Replay salary correction',correction,'salary-payment-correction',op=op)
new=sql("SELECT corrected_by_slip_id FROM salary_slips WHERE id='"+prefix+"'");assert new
check('Original salary retained as corrected',sql("SELECT status FROM salary_slips WHERE id='"+prefix+"'")=='corrected')
post('Corrected original cannot be paid again',paid,expected=False)
post('Cancel corrected salary',{'command':'cancel','slipId':new,'reason':'Local cancellation fixture','confirmation':'BATALKAN GAJI'},'salary-payment-correction')
post('Cancelled slip cannot reopen',{**paid,'id':new,'basicSalary':120000,'bonus':0,'detailedAllowances':[],'detailedDeductions':[],'netSalary':120000},expected=False)
check('Payroll cancellation nets to zero cash',sql("SELECT COALESCE(SUM(CASE WHEN type='income' THEN amount ELSE -amount END),0) FROM transactions WHERE sourceEntityId IN ('"+prefix+"','"+new+"')")=='0.00')
check('Payroll tax classification preserved',sql("SELECT COUNT(*) FROM transactions WHERE sourceEntityId IN ('"+prefix+"','"+new+"') AND (taxAmount<>0 OR taxSnapshotStatus<>'not_applicable')")=='0')
check('Payroll journals balanced',sql('SELECT COUNT(*) FROM (SELECT journal_entry_id FROM journal_lines GROUP BY journal_entry_id HAVING ABS(SUM(debit)-SUM(credit))>0.001) x')=='0')
print('Payroll integration assertions:',len(results))
