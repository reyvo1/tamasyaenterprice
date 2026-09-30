<?php
$c=json_decode(file_get_contents(__DIR__.'/credentials.json'),true);
$pdo=new PDO('mysql:host=127.0.0.1;port=23384;dbname=tamasya_sim;charset=utf8mb4',$c['user'],$c['password'],[PDO::ATTR_ERRMODE=>PDO::ERRMODE_EXCEPTION,PDO::ATTR_DEFAULT_FETCH_MODE=>PDO::FETCH_ASSOC]);
$environment=json_decode(file_get_contents(__DIR__.'/environment.json'),true);
$zone=new DateTimeZone($environment['APP_TIMEZONE']);
$offset=(new DateTimeImmutable('now',$zone))->format('P');
$pdo->exec('SET time_zone = '.$pdo->quote($offset));
$input=json_decode(stream_get_contents(STDIN),true);
$s=$pdo->prepare($input['sql']);$s->execute($input['params']??[]);
echo json_encode($s->columnCount()?$s->fetchAll():['affected'=>$s->rowCount()],JSON_UNESCAPED_UNICODE|JSON_UNESCAPED_SLASHES);
