<?php
if(PHP_SAPI!=='cli'){http_response_code(404);exit;}
define('TAMASYA_API_ENTRY',true);require dirname(__DIR__).'/api/modules/growth_enterprise_locked/111_growth_invariants.php';
$passed=0;
function rejectGrowthInput(callable $f,string $name):void{global $passed;try{$f();}catch(InvalidArgumentException $e){$passed++;echo "PASS $name\n";return;}throw new RuntimeException('FAIL '.$name);}
foreach([true,[],new stdClass(),'not-money',-0.01,INF] as $value)rejectGrowthInput(fn()=>tamasyaGrowthValidateRawInput('pr-save',['items'=>[['quantity'=>1,'estimatedUnitPrice'=>$value]]]),'Reject malformed or negative procurement price '.get_debug_type($value));
foreach([0,-1,true,[]] as $value)rejectGrowthInput(fn()=>tamasyaGrowthValidateRawInput('grn-save',['items'=>[['quantityReceived'=>$value]]]),'Reject invalid GRN quantity '.get_debug_type($value));
rejectGrowthInput(fn()=>tamasyaGrowthValidateRawInput('supplier-invoice-save',['lines'=>[['quantity'=>1,'accountClass'=>'misspelled']]]),'Unknown accounting class rejected');
rejectGrowthInput(fn()=>tamasyaGrowthValidateRawInput('po-save',['items'=>[]]),'Empty PO items rejected');
rejectGrowthInput(fn()=>tamasyaGrowthValidateRawInput('folio-route-save',['routePercent'=>101]),'Excess routing percentage rejected');
rejectGrowthInput(fn()=>tamasyaEnterpriseValidateSegmentCondition(['unknown_filter'=>true]),'Unknown CRM filter fails closed');
rejectGrowthInput(fn()=>tamasyaEnterpriseValidateSegmentCondition(['email_required'=>'false']),'Marketing condition requires actual boolean');
rejectGrowthInput(fn()=>tamasyaEnterpriseValidateSegmentCondition(['tier_in'=>['not-a-tier']]),'Unknown loyalty tier rejected');
rejectGrowthInput(fn()=>tamasyaEnterpriseValidateSegmentCondition(['min_nights'=>-1]),'Negative CRM threshold rejected');
tamasyaGrowthValidateRawInput('supplier-invoice-save',['lines'=>[['quantity'=>1.5,'unitPrice'=>'12.34','taxRate'=>0,'accountClass'=>'inventory']]]);$passed++;echo "PASS Valid decimal procurement inputs\n";
tamasyaEnterpriseValidateSegmentCondition(['email_required'=>true,'tier_in'=>['gold'],'min_nights'=>5]);$passed++;echo "PASS Valid CRM condition\n";
echo "GROWTH INPUT UNIT PASSED $passed\n";
