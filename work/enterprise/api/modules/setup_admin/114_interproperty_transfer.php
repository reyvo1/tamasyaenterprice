<?php
declare(strict_types=1);
if(!defined('TAMASYA_API_ENTRY')){http_response_code(404);exit;}

function tamasyaInterpropertyEnabled():bool{return filter_var(getenv('TAMASYA_INTERPROPERTY_TRANSFER_ENABLED')?:'0',FILTER_VALIDATE_BOOLEAN);}
function tamasyaInterpropertyConfig():array{
    if(!tamasyaInterpropertyEnabled())throw new RuntimeException('Transfer antarproperti belum diaktifkan.');
    $path=realpath((string)getenv('TAMASYA_INTERPROPERTY_KEYS_FILE'));$root=realpath(dirname(__DIR__,3));
    if(!$path||!$root||!is_file($path)||filesize($path)>65536)throw new RuntimeException('Konfigurasi peer transfer private belum tersedia.');
    $normalized=strtolower(str_replace('\\','/',$path));$public=strtolower(str_replace('\\','/',$root));
    if($normalized===$public||str_starts_with($normalized,$public.'/'))throw new RuntimeException('Konfigurasi transfer harus di luar document root.');
    $c=json_decode((string)file_get_contents($path),true,16,JSON_THROW_ON_ERROR);$identity=tamasyaMultiPropertyIdentity();
    if(!is_array($c)||($c['companyId']??null)!==$identity['companyId']||($c['propertyId']??null)!==$identity['propertyId']||!tamasyaHybridId($identity['companyId'])||!is_array($c['peers']??null))throw new RuntimeException('Identitas konfigurasi transfer tidak cocok.');
    return $c;
}
function tamasyaInterpropertyPeerKey(array $config,string $peer):string{
    $p=$config['peers'][$peer]??null;
    if(!tamasyaHybridId($peer)||$peer===$config['propertyId']||!is_array($p)||($p['enabled']??false)!==true||!is_string($p['secret']??null)||strlen($p['secret'])<32)throw new InvalidArgumentException('Properti pasangan tidak diizinkan.');
    return $p['secret'];
}
function tamasyaInterpropertySign(array $payload,string $key,string $kind):array{
    return ['payload'=>$payload,'signature'=>hash_hmac('sha256',$kind."\n".tamasyaHybridJson($payload),$key)];
}
function tamasyaInterpropertyVerify(array $document,array $config,string $kind):array{
    tamasyaHybridKeys($document,['payload','signature']);$p=$document['payload'];
    if(!is_array($p)||!is_string($document['signature']))throw new InvalidArgumentException('Dokumen transfer tidak valid.');
    $keys=['contractVersion','transferId','companyId','sourcePropertyId','destinationPropertyId','currency','amountMinor'];
    $keys=array_merge($keys,$kind==='order'?['sourceTransactionId','sourceDate','reference']:['orderHash','destinationTransactionId','receivedDate']);tamasyaHybridKeys($p,$keys);
    if($p['contractVersion']!==('tamasya-interproperty-'.$kind.'-v1')||$p['companyId']!==$config['companyId'])throw new InvalidArgumentException('Kontrak/perusahaan dokumen tidak cocok.');
    foreach(['transferId','sourcePropertyId','destinationPropertyId'] as $field)if(!tamasyaHybridId($p[$field]))throw new InvalidArgumentException('Identitas dokumen tidak valid.');
    $local=$kind==='order'?'destinationPropertyId':'sourcePropertyId';$remote=$kind==='order'?'sourcePropertyId':'destinationPropertyId';
    if($p[$local]!==$config['propertyId'])throw new InvalidArgumentException('Dokumen bukan untuk properti ini.');
    $key=tamasyaInterpropertyPeerKey($config,$p[$remote]);
    if(!hash_equals(hash_hmac('sha256',$kind."\n".tamasyaHybridJson($p),$key),$document['signature']))throw new InvalidArgumentException('Signature dokumen tidak cocok.');
    if($p['currency']!==tamasyaMultiPropertyIdentity()['currency'])throw new InvalidArgumentException('Mata uang properti berbeda; transfer tanpa kurs hanya untuk mata uang yang sama.');
    if(!is_string($p['amountMinor'])||!preg_match('/^[1-9][0-9]{0,13}$/D',$p['amountMinor'])||(int)$p['amountMinor']>99999999999999)throw new InvalidArgumentException('Nominal dokumen tidak valid.');
    $date=$kind==='order'?$p['sourceDate']:$p['receivedDate'];if(!is_string($date)||!validIsoDate($date))throw new InvalidArgumentException('Tanggal dokumen tidak valid.');
    $tx=$kind==='order'?$p['sourceTransactionId']:$p['destinationTransactionId'];if(!is_string($tx)||!preg_match('/^tx_ip_[a-f0-9]{36}$/D',$tx))throw new InvalidArgumentException('Identitas transaksi dokumen tidak valid.');
    if($kind==='receipt'&&(!is_string($p['orderHash'])||!preg_match('/^[a-f0-9]{64}$/D',$p['orderHash'])))throw new InvalidArgumentException('Fingerprint dokumen sumber tidak valid.');
    if($kind==='order'&&(!is_string($p['reference'])||strlen($p['reference'])<8||strlen($p['reference'])>120))throw new InvalidArgumentException('Referensi bank tidak valid.');
    return $p;
}
function tamasyaInterpropertyPost(PDO $pdo,array $actor,array $payload,string $direction,string $account,string $reference):string{
    tamasyaRequirePropertyReadyForLiveMutation($pdo,'transfer antarproperti');
    $account=tamasyaResolvePaymentAccount($pdo,'transfer',$account,['allowedMethods'=>['transfer'],'lock'=>true,'context'=>'Transfer antarproperti']);
    $amount=((int)$payload['amountMinor'])/100;$tx='tx_ip_'.substr(hash('sha256',$direction.'|'.$payload['transferId']),0,36);
    tamasyaPostFinancialTransaction($pdo,[
        'id'=>$tx,'type'=>$direction==='out'?'expense':'income','amount'=>$amount,'date'=>date('Y-m-d'),
        'category'=>'Transfer Antarproperti','subcategory'=>$direction==='out'?'Dana Keluar':'Dana Masuk',
        'description'=>'Transfer '.$payload['transferId'].' / '.$reference,'createdBy'=>currentStaffLabel($actor),
        'bankAccountId'=>$account,'baseAmount'=>$amount,'taxAmount'=>0,'taxRate'=>0,'taxSnapshotStatus'=>'not_applicable','taxSource'=>'interproperty_transfer',
        'transactionKind'=>'interproperty_transfer_'.$direction,'sourceEntity'=>'interproperty_transfer','sourceEntityId'=>$payload['transferId'],
        'isSystemGenerated'=>1,'operationId'=>'ip:'.$direction.':'.$payload['transferId'],'recordOrigin'=>'live_operation','shiftExempt'=>1,
        'shiftExemptionReason'=>'Transfer antar rekening bank properti','updatedBy'=>$actor['id']??null,'updatedSource'=>'web','version'=>1
    ],$actor,'interproperty_transfer',['source'=>'web']);
    return $tx;
}
function tamasyaInterpropertyPublic(array $row):array{
    foreach(['order_json'=>'order','receipt_json'=>'receipt'] as $column=>$field){$row[$field]=$row[$column]?json_decode($row[$column],true,16,JSON_THROW_ON_ERROR):null;unset($row[$column]);}
    unset($row['request_hash'],$row['business_key']);return $row;
}
function tamasyaInterpropertyMutate(PDO $pdo,array $actor,string $command,array $input,string $op):array{
    if(!preg_match('/^[a-zA-Z0-9._:-]{1,100}$/D',$op))throw new InvalidArgumentException('Operation ID wajib.');
    $config=tamasyaInterpropertyConfig();$identity=tamasyaMultiPropertyIdentity();
    if(!tamasyaGrowthTableExists($pdo,'growth_interproperty_transfers'))throw new RuntimeException('Jalankan migrasi Enterprise pada Primary dan Standby dahulu.');
    $pdo->beginTransaction();
    try{
        tamasyaGrowthRequireWriter();
        if($command==='create'){
            if(($input['confirmation']??'')!=='DANA SUDAH DIKIRIM')throw new InvalidArgumentException('Konfirmasi dana telah dikirim melalui bank terlebih dahulu.');
            $peer=trim((string)($input['destinationPropertyId']??''));$key=tamasyaInterpropertyPeerKey($config,$peer);
            $amount=tamasyaGrowthMoney($input['amount']??0);if($amount<=0||$amount>999999999999.99)throw new InvalidArgumentException('Nominal transfer harus positif.');
            $reference=trim((string)($input['reference']??''));if(strlen($reference)<8||strlen($reference)>120)throw new InvalidArgumentException('Referensi bank wajib 8 sampai 120 karakter.');
            $account=trim((string)($input['bankAccountId']??''));$id='ipt_'.substr(hash('sha256',$identity['companyId'].'|'.$identity['propertyId'].'|'.$op),0,40);
            $requestHash=hash('sha256',tamasyaHybridJson(['peer'=>$peer,'amountMinor'=>tamasyaHybridMinor($amount),'reference'=>$reference,'account'=>$account]));
            $existing=tamasyaEnterpriseFetch($pdo,'SELECT * FROM growth_interproperty_transfers WHERE id=? FOR UPDATE',[$id]);
            if($existing){if(!hash_equals($existing['request_hash'],$requestHash))throw new RuntimeException('Operation ID transfer memiliki isi berbeda.');tamasyaFinancialCommit($pdo);return tamasyaInterpropertyPublic($existing);}
            $payload=['contractVersion'=>'tamasya-interproperty-order-v1','transferId'=>$id,'companyId'=>$identity['companyId'],'sourcePropertyId'=>$identity['propertyId'],'destinationPropertyId'=>$peer,'currency'=>$identity['currency'],'amountMinor'=>tamasyaHybridMinor($amount),'sourceDate'=>date('Y-m-d'),'reference'=>$reference];
            $tx=tamasyaInterpropertyPost($pdo,$actor,$payload,'out',$account,$reference);$payload['sourceTransactionId']=$tx;$order=tamasyaInterpropertySign($payload,$key,'order');
            $businessKey=hash('sha256','out|'.$account.'|'.$reference);
            $pdo->prepare("INSERT INTO growth_interproperty_transfers(id,direction,peer_property_id,currency,amount,reference,bank_account_id,transaction_id,status,request_hash,business_key,order_json,operation_id,created_by) VALUES (?,'out',?,?,?,?,?,?,'awaiting_receipt',?,?,?,?,?)")->execute([$id,$peer,$identity['currency'],$amount,$reference,$account,$tx,$requestHash,$businessKey,tamasyaHybridJson($order),$op,$actor['id']??null]);
        }elseif($command==='receive'){
            if(($input['confirmation']??'')!=='DANA SUDAH DITERIMA')throw new InvalidArgumentException('Konfirmasi dana telah diterima di rekening bank terlebih dahulu.');
            $order=$input['document']??null;if(!is_array($order))throw new InvalidArgumentException('Dokumen sumber wajib.');$payload=tamasyaInterpropertyVerify($order,$config,'order');$id=$payload['transferId'];$orderHash=hash('sha256',tamasyaHybridJson($payload));
            $existing=tamasyaEnterpriseFetch($pdo,'SELECT * FROM growth_interproperty_transfers WHERE id=? FOR UPDATE',[$id]);
            if($existing){if($existing['direction']!=='in'||!hash_equals($existing['request_hash'],$orderHash)||(string)$existing['bank_account_id']!==trim((string)($input['bankAccountId']??''))||(string)$existing['reference']!==trim((string)($input['reference']??'')))throw new RuntimeException('Transfer ID memiliki dokumen, rekening atau referensi berbeda.');tamasyaFinancialCommit($pdo);return tamasyaInterpropertyPublic($existing);}
            $reference=trim((string)($input['reference']??''));if(strlen($reference)<8||strlen($reference)>120)throw new InvalidArgumentException('Referensi penerimaan bank wajib 8 sampai 120 karakter.');
            $account=trim((string)($input['bankAccountId']??''));$tx=tamasyaInterpropertyPost($pdo,$actor,$payload,'in',$account,$reference);
            $receipt=tamasyaInterpropertySign(['contractVersion'=>'tamasya-interproperty-receipt-v1','transferId'=>$id,'companyId'=>$identity['companyId'],'sourcePropertyId'=>$payload['sourcePropertyId'],'destinationPropertyId'=>$identity['propertyId'],'currency'=>$identity['currency'],'amountMinor'=>$payload['amountMinor'],'orderHash'=>$orderHash,'destinationTransactionId'=>$tx,'receivedDate'=>date('Y-m-d')],tamasyaInterpropertyPeerKey($config,$payload['sourcePropertyId']),'receipt');
            $pdo->prepare("INSERT INTO growth_interproperty_transfers(id,direction,peer_property_id,currency,amount,reference,bank_account_id,transaction_id,status,request_hash,business_key,order_json,receipt_json,operation_id,created_by) VALUES (?,'in',?,?,?,?,?,?,'received',?,?,?,?,?,?)")->execute([$id,$payload['sourcePropertyId'],$identity['currency'],((int)$payload['amountMinor'])/100,$reference,$account,$tx,$orderHash,hash('sha256','in|'.$account.'|'.$reference),tamasyaHybridJson($order),tamasyaHybridJson($receipt),$op,$actor['id']??null]);
        }elseif($command==='reconcile'){
            $receipt=$input['document']??null;if(!is_array($receipt))throw new InvalidArgumentException('Bukti penerimaan wajib.');$payload=tamasyaInterpropertyVerify($receipt,$config,'receipt');$id=$payload['transferId'];
            $existing=tamasyaEnterpriseFetch($pdo,'SELECT * FROM growth_interproperty_transfers WHERE id=? FOR UPDATE',[$id]);
            if(!$existing||$existing['direction']!=='out')throw new InvalidArgumentException('Transfer keluar sumber tidak ditemukan.');
            $order=json_decode($existing['order_json'],true,16,JSON_THROW_ON_ERROR)['payload'];
            if(!hash_equals(hash('sha256',tamasyaHybridJson($order)),(string)$payload['orderHash'])||$payload['destinationPropertyId']!==$order['destinationPropertyId']||$payload['amountMinor']!==$order['amountMinor'])throw new RuntimeException('Bukti penerimaan tidak cocok dengan transaksi sumber.');
            if($existing['receipt_json']!==null&&$existing['receipt_json']!==tamasyaHybridJson($receipt))throw new RuntimeException('Bukti rekonsiliasi sudah final dan berbeda.');
            $pdo->prepare("UPDATE growth_interproperty_transfers SET status='reconciled',receipt_json=?,reconciled_at=COALESCE(reconciled_at,CURRENT_TIMESTAMP) WHERE id=?")->execute([tamasyaHybridJson($receipt),$id]);
        }else throw new InvalidArgumentException('Perintah transfer tidak dikenal.');
        $row=tamasyaEnterpriseFetch($pdo,'SELECT * FROM growth_interproperty_transfers WHERE id=?',[$id]);
        tamasyaGrowthAudit($pdo,$actor,'Transfer antarproperti '.$command,'interproperty_transfer',$id,null,['direction'=>$row['direction'],'status'=>$row['status'],'transactionId'=>$row['transaction_id']]);
        bumpServerRevision($pdo);tamasyaFinancialCommit($pdo);return tamasyaInterpropertyPublic($row);
    }catch(Throwable $error){if($pdo->inTransaction())$pdo->rollBack();throw $error;}
}
