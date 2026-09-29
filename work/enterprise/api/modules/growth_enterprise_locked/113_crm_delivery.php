<?php
declare(strict_types=1);
if (!defined('TAMASYA_API_ENTRY')) { http_response_code(404); exit; }

/** Durable claim before SMTP. An ambiguous outcome requires reconciliation, never automatic retry. */
function tamasyaEnterpriseSendCampaignBatch(PDO $pdo,string $id,int $limit,array $staff,?callable $sender=null): array {
    if($pdo->inTransaction())throw new RuntimeException('Campaign sender requires its own transaction.');
    $limit=max(1,min(20,$limit));
    $config=tamasyaEnterpriseFetch($pdo,"SELECT smtp_host,smtp_port,smtp_user,smtp_password,smtp_secure,smtp_from FROM config WHERE id='system_default'")?:[];
    if(!$sender&&trim((string)($config['smtp_host']??''))==='')throw new RuntimeException('SMTP belum dikonfigurasi.');
    $sender=$sender??'sendSmtpMail';
    $sent=0;$blocked=0;$uncertain=0;
    for($index=0;$index<$limit;$index++){
        $pdo->beginTransaction();
        try{
            tamasyaGrowthRequireWriter();
            $campaign=tamasyaEnterpriseFetch($pdo,"SELECT * FROM growth_crm_campaigns WHERE id=? FOR UPDATE",[$id]);
            if(!$campaign||!in_array($campaign['status'],['ready','completed'],true))throw new RuntimeException('Campaign harus ready dan recipient snapshot sudah dibuat.');
            if($campaign['channel']!=='email')throw new RuntimeException('Batch sender otomatis hanya mendukung email.');
            $r=tamasyaEnterpriseFetch($pdo,"SELECT * FROM growth_crm_campaign_recipients WHERE campaign_id=? AND status='pending' ORDER BY queued_at,id LIMIT 1 FOR UPDATE",[$id]);
            if(!$r){tamasyaFinancialCommit($pdo);break;}
            // Consent writers also lock guest_profiles, so destination and consent are checked together.
            $guest=tamasyaEnterpriseFetch($pdo,"SELECT id,email,name FROM guest_profiles WHERE id=? FOR UPDATE",[$r['guest_profile_id']]);
            $email=trim((string)($guest['email']??''));
            $cons=tamasyaEnterpriseActiveConsent($pdo,(string)$r['guest_profile_id'],'email_marketing');
            $validDest=$email!==''&&filter_var($email,FILTER_VALIDATE_EMAIL)&&hash_equals((string)$r['destination_hash'],hash('sha256',strtolower($email)));
            if(!$cons||!$validDest){
                $pdo->prepare("UPDATE growth_crm_campaign_recipients SET status='blocked',last_error=? WHERE id=?")->execute([$cons?'Alamat berubah; snapshot ulang diperlukan.':'Consent email marketing tidak aktif.',$r['id']]);
                bumpServerRevision($pdo);tamasyaFinancialCommit($pdo);$blocked++;continue;
            }
            $pdo->prepare("UPDATE growth_crm_campaign_recipients SET status='sending',last_error=NULL WHERE id=?")->execute([$r['id']]);
            tamasyaGrowthAudit($pdo,$staff,'Mengklaim penerima campaign sebelum SMTP','growth_crm_campaign_recipient',$r['id'],$r,['status'=>'sending']);
            bumpServerRevision($pdo);tamasyaFinancialCommit($pdo);
        }catch(Throwable $e){if($pdo->inTransaction())$pdo->rollBack();throw $e;}
        $subject=trim((string)($campaign['subject']??''))?:'Informasi Hotel';
        $name=htmlspecialchars((string)$guest['name'],ENT_QUOTES,'UTF-8');
        $body=str_replace(['{{guest_name}}','{{member_name}}'],[$name,$name],(string)$campaign['message_template']);
        $status='uncertain';$error='Hasil SMTP belum pasti; verifikasi pengiriman sebelum tindakan manual.';
        try{
            tamasyaGrowthRequireWriter();
            if($sender($email,$subject,$body,$config)===true){$status='sent';$error=null;}
        }catch(Throwable $mailError){
            // Keep credentials and transport diagnostics out of the recipient record.
        }
        $pdo->beginTransaction();
        try{
            $pdo->prepare("UPDATE growth_crm_campaign_recipients SET status=?,last_error=?,sent_at=CASE WHEN ?='sent' THEN CURRENT_TIMESTAMP ELSE NULL END WHERE id=? AND status='sending'")->execute([$status,$error,$status,$r['id']]);
            tamasyaGrowthAudit($pdo,$staff,'Mencatat hasil SMTP campaign','growth_crm_campaign_recipient',$r['id'],['status'=>'sending'],['status'=>$status]);
            bumpServerRevision($pdo);tamasyaFinancialCommit($pdo);
        }catch(Throwable $e){if($pdo->inTransaction())$pdo->rollBack();throw $e;}
        if($status==='sent')$sent++;else $uncertain++;
    }
    $pdo->beginTransaction();
    try{
        tamasyaEnterpriseFetch($pdo,"SELECT id FROM growth_crm_campaigns WHERE id=? FOR UPDATE",[$id]);
        $rows=tamasyaEnterpriseFetchAll($pdo,"SELECT status,COUNT(*) total FROM growth_crm_campaign_recipients WHERE campaign_id=? GROUP BY status",[$id]);
        $counts=[];foreach($rows as $row)$counts[$row['status']]=(int)$row['total'];
        $remaining=($counts['pending']??0);$review=($counts['sending']??0)+($counts['uncertain']??0)+($counts['failed']??0)+($counts['blocked']??0);
        $pdo->prepare("UPDATE growth_crm_campaigns SET status=? WHERE id=?")->execute([$remaining===0&&$review===0?'completed':'ready',$id]);
        bumpServerRevision($pdo);tamasyaFinancialCommit($pdo);
    }catch(Throwable $e){if($pdo->inTransaction())$pdo->rollBack();throw $e;}
    return ['sent'=>$sent,'blocked'=>$blocked,'uncertain'=>$uncertain,'failed'=>$blocked+$uncertain,'remaining'=>$remaining,'requiresReview'=>$review];
}
