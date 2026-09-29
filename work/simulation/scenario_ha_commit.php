<?php
declare(strict_types=1);
if(PHP_SAPI!=='cli')exit(1);
putenv('NODE_CLUSTER_ENABLED=0');putenv('TAMASYA_NODE_MODE=');
$_SERVER['REQUEST_METHOD']='GET';$_SERVER['HTTP_HOST']='127.0.0.1:38184';$_SERVER['REMOTE_ADDR']='127.0.0.1';$_GET=['action'=>'test-bootstrap'];
define('TAMASYA_SERVICE_BOOTSTRAP',true);ob_start();require __DIR__.'/site/api.php';ob_end_clean();
restore_exception_handler();
if((int)$pdo->query('SELECT @@port')->fetchColumn()!==33384||$pdo->query('SELECT DATABASE()')->fetchColumn()!=='tamasya_sim')throw new RuntimeException('Local simulation database required.');
// Session-local temporary tables shadow only cluster metadata, never hotel records.
foreach(['node_cluster_state','node_cluster_members','node_sync_settings','node_cluster_events'] as $table){$ddl=$pdo->query('SHOW CREATE TABLE `'.$table.'`')->fetch(PDO::FETCH_NUM)[1];$pdo->exec(preg_replace('/^CREATE TABLE /','CREATE TEMPORARY TABLE ',$ddl));}
$pdo->exec('CREATE TEMPORARY TABLE ha_commit_probe(id int PRIMARY KEY) ENGINE=InnoDB');
putenv('NODE_CLUSTER_ENABLED=1');putenv('NODE_CLUSTER_PROBE_BEFORE_WRITE=0');putenv('TAMASYA_CLUSTER_ID=local-ha-commit-test');putenv('NODE_CLUSTER_PEER_ID=sim-standby');putenv('NODE_CLUSTER_PEER_URL=');
$results=[];
function checkHa(string $name,bool $ok):void {global $results;$results[]=['name'=>$name,'pass'=>$ok];if(!$ok)throw new RuntimeException($name);}
try{
 tamasyaInitializeClusterState($pdo);
 checkHa('Active writer has valid lease',tamasyaClusterMutationGuard($pdo)===null);
 $pdo->beginTransaction();$pdo->exec('INSERT INTO ha_commit_probe VALUES (1)');tamasyaFinancialCommit($pdo);checkHa('Canonical commit succeeds with matching authority',(int)$pdo->query('SELECT COUNT(*) FROM ha_commit_probe')->fetchColumn()===1);
 $states=[
  'expired lease'=>"lease_expires_at='2000-01-01 00:00:00'",
  'different epoch'=>'leadership_epoch=leadership_epoch+1',
  'different fencing token'=>"fencing_token='replacement-fence'",
  'different writer'=>"current_primary_node_id='sim-standby'",
  'draining'=>"transfer_state='draining'",
  'split brain'=>"transfer_state='split_brain'",
 ];
 foreach($states as $name=>$sql){
  checkHa('Writer guard before '.$name,tamasyaClusterMutationGuard($pdo)===null);
  $pdo->beginTransaction();$pdo->exec('INSERT INTO ha_commit_probe VALUES (2)');$pdo->exec("UPDATE node_cluster_state SET $sql WHERE id='system_default'");
  $blocked=false;try{tamasyaFinancialCommit($pdo);}catch(RuntimeException $e){$blocked=str_contains($e->getMessage(),'COMMIT_FENCED');}finally{if($pdo->inTransaction())$pdo->rollBack();}
  checkHa('Canonical commit rejects '.$name,$blocked);
  checkHa('Rejected '.$name.' leaves no committed probe',(int)$pdo->query('SELECT COUNT(*) FROM ha_commit_probe')->fetchColumn()===1);
 }
 $pdo->exec("UPDATE node_cluster_state SET current_primary_node_id='sim-standby',lease_owner_node_id='sim-standby' WHERE id='system_default'");
 checkHa('Standby mutation guard rejects writes',tamasyaClusterMutationGuard($pdo)!==null);
 checkHa('Standby suppresses side effects',!tamasyaExternalSideEffectsAllowed());
 $blocked=false;try{tamasyaClusterEmergencyPromote($pdo,['id'=>'test'],'Local test without isolation confirmation',false,false,false);}catch(InvalidArgumentException $e){$blocked=true;}
 checkHa('No emergency promotion without isolation and backup confirmations',$blocked);
 putenv('NODE_CLUSTER_ENABLED=0');checkHa('Optional cluster disabled preserves shared-hosting path',tamasyaClusterMutationGuard($pdo)===null);
}finally{if($pdo->inTransaction())$pdo->rollBack();file_put_contents(__DIR__.'/ha-commit-results.json',json_encode($results,JSON_PRETTY_PRINT));}
echo 'HA commit assertions passed: '.count($results)."\n";
