<?php
if(PHP_SAPI!=='cli'){http_response_code(404);exit;}
require dirname(__DIR__).'/hybrid_contract.php';
$count=0;
function v3check(bool $ok,string $name):void{global $count;if(!$ok)throw new RuntimeException('FAIL '.$name);$count++;echo "PASS $name\n";}
function v3reject(callable $f,string $name):void{try{$f();}catch(InvalidArgumentException $e){v3check(true,$name);return;}v3check(false,$name);}
$s=['contractVersion'=>'tamasya-hq-snapshot-v3','companyId'=>'test-company','propertyId'=>'hotel-a','propertyName'=>'Hotel A','currency'=>'IDR','timezone'=>'Asia/Makassar','period'=>['from'=>'2026-09-01','to'=>'2026-09-22'],'sourceRevision'=>1,'metricsMinor'=>array_fill_keys(tamasyaHybridMetricNames('tamasya-hq-snapshot-v3'),'0'),'roomNights'=>['sold'=>0,'available'=>1],'integrity'=>['status'=>'PASS','unresolvedTaxCount'=>0,'pendingHistoricalCount'=>0,'openSyncConflicts'=>0]];
$s['metricsMinor']=array_replace($s['metricsMinor'],['payrollExpense'=>'12345','guestReceivableBalance'=>'5000','otaReceivableBalance'=>'7000','accountsReceivableBalance'=>'12000','accountsPayableBalance'=>'8000']);
$s['checksumSha256']=tamasyaHybridChecksum($s);tamasyaHybridValidate($s);v3check(true,'Strict enterprise snapshot v3');
$old=$s;$old['contractVersion']='tamasya-hq-snapshot-v2';$old['metricsMinor']=array_intersect_key($old['metricsMinor'],array_flip(tamasyaHybridMetricNames()));$old['checksumSha256']=tamasyaHybridChecksum($old);
v3check(tamasyaHybridCompatibleUpgrade($old,$s),'Same revision permits additive v2 to v3 upgrade');
v3check(!tamasyaHybridCompatibleUpgrade($s,$old),'Same revision never downgrades');
$bad=$s;$bad['metricsMinor']['expense']='1';$bad['metricsMinor']['profit']='-1';$bad['checksumSha256']=tamasyaHybridChecksum($bad);v3check(!tamasyaHybridCompatibleUpgrade($old,$bad),'Upgrade cannot change prior financial evidence');
$bad=$s;$bad['metricsMinor']['accountsReceivableBalance']='12001';$bad['checksumSha256']=tamasyaHybridChecksum($bad);v3reject(fn()=>tamasyaHybridValidate($bad),'Receivable components must reconcile');
$bad=$s;unset($bad['metricsMinor']['payrollExpense']);$bad['checksumSha256']=tamasyaHybridChecksum($bad);v3reject(fn()=>tamasyaHybridValidate($bad),'Missing v3 metric is not silently zero');
$other=$s;$other['propertyId']='hotel-b';$other['checksumSha256']=tamasyaHybridChecksum($other);
$report=tamasyaHybridConsolidate([$s,$other],['hotel-a','hotel-b'],'test-company','2026-09-01','2026-09-22');
v3check($report['currencies']['IDR']['metricsMinor']['payrollExpense']==='24690','Payroll sums exact integer cents');
v3check($report['currencies']['IDR']['metricsMinor']['accountsReceivableBalance']==='24000'&&$report['currencies']['IDR']['metricsMinor']['accountsPayableBalance']==='16000','AR AP consolidated correctly');
$mixed=tamasyaHybridConsolidate([$old,$other],['hotel-a','hotel-b'],'test-company','2026-09-01','2026-09-22');
v3check(!isset($mixed['currencies']['IDR']['metricsMinor']['payrollExpense'])&&$mixed['integrityStatus']==='INCOMPLETE','Mixed versions never report partial payroll as complete');
v3check($mixed['currencies']['IDR']['metricCoverage']['payrollExpense']['availableProperties']===1,'Mixed-version metric coverage explicit');
$other['currency']='USD';$other['checksumSha256']=tamasyaHybridChecksum($other);
$fx=tamasyaHybridConsolidate([$s,$other],['hotel-a','hotel-b'],'test-company','2026-09-01','2026-09-22');v3check(count($fx['currencies'])===2&&$fx['currencies']['USD']['metricsMinor']['payrollExpense']==='12345','Currencies remain separate without FX assumptions');
echo "HQ V3 UNIT PASSED $count\n";
