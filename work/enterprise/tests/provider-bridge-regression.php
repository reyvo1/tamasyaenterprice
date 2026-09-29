<?php
if(PHP_SAPI!=='cli'){http_response_code(404);exit;}
define('TAMASYA_API_ENTRY',true);
require __DIR__.'/../api/modules/growth_enterprise_locked/117_provider_bridge.php';
$secret=str_repeat('local-fixture-key-',3);$now=1800000000;$n=0;
$scope=['companyId'=>'fixture','propertyId'=>'hotel-a','providerCode'=>'mock','adapterType'=>'payment','currency'=>'IDR'];
$body=$scope+['eventId'=>'evt-1','issuedAt'=>$now,'expiresAt'=>$now+120,'eventType'=>'payment.status','payload'=>['intentId'=>'pi-1','status'=>'paid','amountMinor'=>12345]];
function envelope(array $body):array{global $secret;$encoded=base64_encode(json_encode($body,JSON_THROW_ON_ERROR));return ['version'=>'tamasya-provider-bridge-v1','body'=>$encoded,'signature'=>hash_hmac('sha256',"tamasya-provider-bridge-v1\n".$encoded,$secret)];}
function check(string $name,bool $ok):void{global $n;if(!$ok)throw new RuntimeException($name);++$n;echo "PASS $name\n";}
function reject(string $name,array $body):void{global $scope,$secret,$now;try{tamasyaBridgeValidate(envelope($body),$secret,$scope,$now);}catch(Throwable $e){check($name,true);return;}check($name,false);}
$a=tamasyaBridgeValidate(envelope($body),$secret,$scope,$now);check('valid payment retains exact cents',$a['body']['payload']['amountMinor']===12345);
check('validation never posts or claims provider verification',!$a['financialMutation']&&!$a['bookingMutation']&&!$a['providerSignatureVerified']);
foreach(['companyId','propertyId','providerCode','currency','adapterType'] as $key)reject('scope '.$key,array_replace($body,[$key=>'other']));
foreach([true,123.45,'12345',0,-1,1000000000000000] as $amount){$bad=$body;$bad['payload']['amountMinor']=$amount;reject('invalid amount '.json_encode($amount),$bad);}
foreach([['issuedAt'=>$now+31],['issuedAt'=>$now-301],['expiresAt'=>$now],['expiresAt'=>$now+301],['issuedAt'=>(string)$now]] as $change)reject('invalid delivery window '.json_encode($change),array_replace($body,$change));
$bad=$body;$bad['payload']['status']='settled-unknown';reject('unknown payment state',$bad);
$bad=$body;$bad['payload']['transactionId']='forbidden';reject('canonical write fields prohibited',$bad);
$bad=envelope($body);$bad['signature']=str_repeat('0',64);
try{tamasyaBridgeValidate($bad,$secret,$scope,$now);check('bad signature',false);}catch(InvalidArgumentException $e){check('bad signature',true);}
$retry=$body;$retry['issuedAt']++;$retry['expiresAt']++;
$b=tamasyaBridgeValidate(envelope($retry),$secret,$scope,$now);
check('redelivery with fresh signature retains event identity',$a['eventKey']===$b['eventKey']&&$a['contentHash']===$b['contentHash']);
$changed=$body;$changed['payload']['amountMinor']++;$c=tamasyaBridgeValidate(envelope($changed),$secret,$scope,$now);
check('same ID different content exposes replay conflict',$a['eventKey']===$c['eventKey']&&$a['contentHash']!==$c['contentHash']);
$channel=$body;$channel['adapterType']='channel';$scope['adapterType']='channel';$channel['eventType']='reservation.created';
$channel['payload']=['externalReservationId'=>'OTA-1','externalRoomType'=>'DELUXE','checkIn'=>'2026-10-01','checkOut'=>'2026-10-03','totalMinor'=>30000000];
check('valid channel event validates without booking mutation',!tamasyaBridgeValidate(envelope($channel),$secret,$scope,$now)['bookingMutation']);
$bad=$channel;$bad['payload']['checkIn']='2026-02-30';reject('invalid calendar day',$bad);
$bad=$channel;$bad['payload']['checkOut']=$bad['payload']['checkIn'];reject('zero length stay',$bad);
$bad=$channel;$bad['eventType']='reservation.delete';reject('unknown channel action',$bad);
echo json_encode(['assertions'=>$n,'passed'=>$n],JSON_THROW_ON_ERROR)."\n";
