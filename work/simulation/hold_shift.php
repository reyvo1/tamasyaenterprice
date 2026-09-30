<?php
$c=json_decode(file_get_contents(__DIR__.'/credentials.json'),true);
$p=new PDO('mysql:host=127.0.0.1;port=23384;dbname=tamasya_sim;charset=utf8mb4',$c['user'],$c['password'],[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION]);
$p->beginTransaction();$p->query("SELECT id FROM shift_sessions WHERE status='open' FOR UPDATE")->fetchAll();
echo "LOCKED\n";flush();sleep(4);$p->rollBack();
