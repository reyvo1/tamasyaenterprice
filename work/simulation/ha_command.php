<?php
declare(strict_types=1);
if(PHP_SAPI!=='cli')exit(1);
$url=parse_url((string)getenv('APP_URL'));$_SERVER['REQUEST_METHOD']='GET';$_SERVER['HTTP_HOST']=$url['host'].':'.$url['port'];$_SERVER['REMOTE_ADDR']='127.0.0.1';$_GET=['action'=>'worker-bootstrap'];
define('TAMASYA_SERVICE_BOOTSTRAP',true);ob_start();require __DIR__.'/site/api.php';ob_end_clean();restore_exception_handler();
if((int)$pdo->query('SELECT @@port')->fetchColumn()!==23384||!str_starts_with((string)$pdo->query('SELECT DATABASE()')->fetchColumn(),'tamasya_ha_test_'))throw new RuntimeException('Dedicated local HA test database required.');
$actor=$pdo->query("SELECT id,name,role FROM staff WHERE role='admin' LIMIT 1")->fetch(PDO::FETCH_ASSOC);
$command=$argv[1]??'status';
switch($command){
 case 'status':$out=tamasyaClusterPublicState($pdo);break;
 case 'checksum':$out=tamasyaClusterDatasetChecksum($pdo);break;
 case 'adopt':$out=tamasyaClusterAdoptHigherPeerEpoch($pdo,$actor);break;
 case 'switch':$out=tamasyaClusterPlannedSwitch($pdo,$actor,'Planned local HA regression switch with synchronized snapshots');break;
 case 'guard':$out=['blocked'=>tamasyaClusterMutationGuard($pdo)!==null,'sideEffects'=>tamasyaExternalSideEffectsAllowed()];break;
 default:throw new RuntimeException('Unknown test command.');
}
echo json_encode($out,JSON_UNESCAPED_SLASHES)."\n";
