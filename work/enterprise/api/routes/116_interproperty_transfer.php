<?php
if(!defined('TAMASYA_API_ENTRY')){http_response_code(404);exit;}
if(($action??'')!=='interproperty-transfer')return;
$routeHandled=true;
requireRoles($loggedInStaff,['admin','manager','finance']);requireDesktopTabAccess($loggedInStaff,'finance',['admin','manager','finance']);
try{
    $method=$_SERVER['REQUEST_METHOD'];
    if($method==='GET'){
        if(!tamasyaInterpropertyEnabled()){echo tamasyaJsonEncode(['success'=>true,'data'=>['enabled'=>false,'rows'=>[]]]);return;}
        $config=tamasyaInterpropertyConfig();$peers=[];foreach($config['peers'] as $id=>$peer)if(($peer['enabled']??false)===true)$peers[]=$id;
        $offset=max(0,min(100000,(int)($_GET['offset']??0)));$rows=tamasyaEnterpriseFetchAll($pdo,'SELECT * FROM growth_interproperty_transfers ORDER BY created_at DESC,id LIMIT 50 OFFSET '.$offset);
        $accounts=tamasyaEnterpriseFetchAll($pdo,"SELECT id,name FROM bank_accounts WHERE isActive=1 AND type='bank' ORDER BY name");
        echo tamasyaJsonEncode(['success'=>true,'data'=>['enabled'=>true,'identity'=>tamasyaMultiPropertyIdentity(),'actorId'=>(string)$loggedInStaff['id'],'peers'=>$peers,'bankAccounts'=>$accounts,'rows'=>array_map('tamasyaInterpropertyPublic',$rows),'nextOffset'=>count($rows)===50?$offset+50:null]]);return;
    }
    if($method!=='POST'){http_response_code(405);echo tamasyaJsonEncode(['success'=>false,'error'=>'Method not allowed']);return;}
    $data=tamasyaInterpropertyMutate($pdo,$loggedInStaff,(string)($input['command']??''),(array)$input,(string)($input['operationId']??''));
    echo tamasyaJsonEncode(['success'=>true,'data'=>$data,'bankNetworkMutation'=>false]);
}catch(Throwable $error){if($pdo->inTransaction())$pdo->rollBack();tamasyaApplyExceptionHttpStatus($error,$error instanceof InvalidArgumentException?422:409);echo tamasyaJsonEncode(['success'=>false,'error'=>clientExceptionMessage('Transfer antarproperti gagal',$error)]);}
