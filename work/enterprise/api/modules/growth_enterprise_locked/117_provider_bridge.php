<?php
/** Provider-neutral bridge validation. This module never posts money or bookings. */
if (!defined('TAMASYA_API_ENTRY')) { http_response_code(404); exit; }

function tamasyaBridgeValidate(array $envelope, string $secret, array $scope, ?int $now=null): array {
    $now??=time();
    if(strlen($secret)<32)throw new InvalidArgumentException('Bridge key requires at least 32 bytes.');
    $keys=array_keys($envelope);sort($keys);
    if($keys!==['body','signature','version']||$envelope['version']!=='tamasya-provider-bridge-v1'
        ||!is_string($envelope['body'])||strlen($envelope['body'])>65536
        ||!is_string($envelope['signature'])||!preg_match('/^[a-f0-9]{64}$/D',$envelope['signature']))
        throw new InvalidArgumentException('Invalid bridge envelope.');
    $raw=base64_decode($envelope['body'],true);
    if($raw===false||base64_encode($raw)!==$envelope['body'])throw new InvalidArgumentException('Body must use canonical base64.');
    // Sign the exact encoded bytes: no cross-language JSON canonicalization assumptions.
    $expected=hash_hmac('sha256',"tamasya-provider-bridge-v1\n".$envelope['body'],$secret);
    if(!hash_equals($expected,$envelope['signature']))throw new InvalidArgumentException('Bridge signature mismatch.');
    $body=json_decode($raw,true,16,JSON_THROW_ON_ERROR);
    if(!is_array($body)||array_is_list($body))throw new InvalidArgumentException('Bridge body must be an object.');
    $required=['companyId','propertyId','providerCode','adapterType','eventId','issuedAt','expiresAt','currency','eventType','payload'];
    $keys=array_keys($body);sort($keys);sort($required);
    if($keys!==$required)throw new InvalidArgumentException('Unknown or missing bridge body field.');
    foreach(['companyId','propertyId','providerCode','adapterType','eventId','currency','eventType'] as $key)
        if(!is_string($body[$key])||!preg_match('/^[A-Za-z0-9_.:-]{1,120}$/D',$body[$key]))throw new InvalidArgumentException('Invalid bridge identifier.');
    foreach(['companyId','propertyId','providerCode','adapterType','currency'] as $key)
        if(!isset($scope[$key])||$body[$key]!==$scope[$key])throw new InvalidArgumentException('Bridge scope mismatch: '.$key);
    if(!preg_match('/^[A-Z]{3}$/D',$body['currency']))throw new InvalidArgumentException('Invalid currency.');
    if(!is_int($body['issuedAt'])||!is_int($body['expiresAt'])||$body['issuedAt']>$now+30
        ||$body['issuedAt']<$now-300||$body['expiresAt']<=$now
        ||$body['expiresAt']<=$body['issuedAt']||$body['expiresAt']-$body['issuedAt']>300)
        throw new InvalidArgumentException('Bridge envelope expired or outside delivery window.');
    $payload=$body['payload'];
    if(!is_array($payload)||array_is_list($payload))throw new InvalidArgumentException('Invalid bridge payload.');
    if($body['adapterType']==='payment'){
        $fields=['amountMinor','intentId','status'];$keys=array_keys($payload);sort($keys);
        if($keys!==$fields||$body['eventType']!=='payment.status'
            ||!is_string($payload['intentId'])||!preg_match('/^[A-Za-z0-9_.:-]{1,120}$/D',$payload['intentId'])
            ||!in_array($payload['status'],['pending','paid','failed','cancelled'],true)
            ||!is_int($payload['amountMinor'])||$payload['amountMinor']<=0||$payload['amountMinor']>999999999999999)
            throw new InvalidArgumentException('Invalid payment bridge payload.');
    }elseif($body['adapterType']==='channel'){
        $fields=['checkIn','checkOut','externalReservationId','externalRoomType','totalMinor'];$keys=array_keys($payload);sort($keys);
        if($keys!==$fields||!in_array($body['eventType'],['reservation.created','reservation.updated','reservation.cancelled'],true))throw new InvalidArgumentException('Invalid channel event.');
        foreach(['externalReservationId','externalRoomType'] as $key)
            if(!is_string($payload[$key])||!preg_match('/^[A-Za-z0-9_.:-]{1,120}$/D',$payload[$key]))throw new InvalidArgumentException('Invalid channel identifier.');
        foreach(['checkIn','checkOut'] as $key){
            if(!is_string($payload[$key]))throw new InvalidArgumentException('Invalid stay date.');
            $date=DateTimeImmutable::createFromFormat('!Y-m-d',$payload[$key]);
            if(!$date||$date->format('Y-m-d')!==$payload[$key])throw new InvalidArgumentException('Invalid stay date.');
        }
        if($payload['checkOut']<=$payload['checkIn']||!is_int($payload['totalMinor'])||$payload['totalMinor']<0||$payload['totalMinor']>999999999999999)throw new InvalidArgumentException('Invalid channel stay or amount.');
    }else throw new InvalidArgumentException('Unsupported adapter type.');
    // Stable semantic identity excludes the short-lived transport timestamps.
    $identity=[];foreach(['companyId','propertyId','providerCode','adapterType','eventId','currency','eventType'] as $key)$identity[$key]=$body[$key];
    ksort($payload);$identity['payload']=$payload;
    return ['body'=>$body,'eventKey'=>hash('sha256',json_encode(array_intersect_key($identity,array_flip(['companyId','propertyId','providerCode','adapterType','eventId'])),JSON_THROW_ON_ERROR)),
        'contentHash'=>hash('sha256',json_encode($identity,JSON_THROW_ON_ERROR|JSON_UNESCAPED_SLASHES)),
        'bridgeSignatureValid'=>true,'providerSignatureVerified'=>false,'financialMutation'=>false,'bookingMutation'=>false];
}

function tamasyaEnterpriseBridgeValidate(PDO $pdo,string $adapterId,array $envelope):array{
    $row=tamasyaEnterpriseFetch($pdo,'SELECT * FROM growth_provider_adapters WHERE id=?',[$adapterId]);
    if(!$row||(int)$row['active']!==1||$row['mode']!=='sandbox')throw new InvalidArgumentException('Bridge simulation requires an active sandbox adapter.');
    if(!in_array($row['webhook_verifier'],['hmac_sha256','sha256_hmac'],true))throw new InvalidArgumentException('Bridge simulation requires HMAC SHA256.');
    $ref=(string)$row['credential_reference'];
    if(!preg_match('/^env:([A-Z][A-Z0-9_]{0,119})$/D',$ref,$match))throw new InvalidArgumentException('Invalid bridge credential reference.');
    $secret=getenv($match[1]);if($secret===false)throw new InvalidArgumentException('Bridge credential unavailable.');
    $scope=tamasyaMultiPropertyIdentity();$scope['providerCode']=$row['provider_code'];$scope['adapterType']=$row['adapter_type'];
    $result=tamasyaBridgeValidate($envelope,$secret,$scope);
    unset($result['body']);
    return $result+['status'=>'validated_only','durablyAccepted'=>false,'simulation'=>true];
}
