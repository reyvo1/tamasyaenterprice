<?php
declare(strict_types=1);
$site=dirname(__DIR__).'/simulation-growth/site';
if(PHP_SAPI!=='cli'||!str_starts_with((string)getenv('APP_EXPECTED_DB_NAME'),'tamasya_growth_test_'))exit(2);
require_once $site.'/database_bootstrap.php';
$_SERVER['REQUEST_METHOD']='GET';$_SERVER['HTTP_HOST']='127.0.0.1:28189';
$_SERVER['REMOTE_ADDR']='127.0.0.1';$_SERVER['REQUEST_URI']='/api.php?action=worker-bootstrap';$_GET=['action'=>'worker-bootstrap'];
define('TAMASYA_SERVICE_BOOTSTRAP',true);
ob_start();require $site.'/api.php';ob_end_clean();
if((int)$pdo->query('SELECT @@port')->fetchColumn()!==23384)exit(3);
$staff=$pdo->query("SELECT * FROM staff WHERE role='admin' LIMIT 1")->fetch(PDO::FETCH_ASSOC);
$sender=static function(string $email,string $subject,string $body,array $config)use($argv):bool{
    if(!str_ends_with($email,'@example.invalid'))throw new RuntimeException('Non-fixture destination denied.');
    file_put_contents($argv[2],json_encode(['destination'=>$email])."\n",FILE_APPEND|LOCK_EX);
    usleep(150000);
    if(str_contains($email,'throw'))throw new RuntimeException('Simulated uncertain response');
    return !str_contains($email,'false');
};
echo json_encode(tamasyaEnterpriseSendCampaignBatch($pdo,$argv[1],20,$staff,$sender));
