<?php
if (!defined('TAMASYA_API_ENTRY')) { http_response_code(404); exit; }
require_once dirname(__DIR__, 3) . '/hybrid_contract.php';

function tamasyaHybridAssertRequestScope(array $identity, array $headers): void {
    foreach (['HTTP_X_TAMASYA_COMPANY_ID'=>'companyId','HTTP_X_TAMASYA_PROPERTY_ID'=>'propertyId'] as $header=>$field) {
        if (!array_key_exists($header, $headers)) continue;
        $value = $headers[$header];
        if (!tamasyaHybridId($value) || $value !== ($identity[$field] ?? null)) throw new InvalidArgumentException('Company/property scope request tidak cocok dengan database hotel.');
    }
}
function tamasyaHybridCapabilities(): array {
    return ['contractVersion'=>'tamasya-capabilities-v1','authority'=>'php-canonical-core','isolation'=>'database-per-property','snapshotVersion'=>'tamasya-hq-snapshot-v3','supportedSnapshotVersions'=>['tamasya-hq-snapshot-v2','tamasya-hq-snapshot-v3'],'hqReadModel'=>true,'redisRequired'=>false,'cronRequired'=>false,'workerRequired'=>false,'financialWorkerWrite'=>false,'crossPropertyWrite'=>false,'realtimeService'=>false,'deploymentProfile'=>'shared-hosting-compatible','maximumSnapshotDays'=>400,'maximumConsolidatedProperties'=>50,'scope'=>tamasyaMultiPropertyIdentity()];
}
function tamasyaHybridSnapshot(PDO $pdo, string $from, string $to,string $version='tamasya-hq-snapshot-v3'): array {
    tamasyaHybridMetricNames($version);
    tamasyaHybridRange($from, $to);
    if ($pdo->inTransaction()) throw new RuntimeException('Snapshot harus memakai transaksi baca tersendiri.');
    // Repeatable read pins identity, revision and every aggregate to one DB view.
    $pdo->exec('SET TRANSACTION ISOLATION LEVEL REPEATABLE READ');
    $pdo->exec('SET TRANSACTION READ ONLY');
    $pdo->beginTransaction();
    try {
        $identity = tamasyaMultiPropertyIdentity();
        if (!tamasyaHybridId($identity['companyId']) || !tamasyaHybridId($identity['propertyId'])) throw new InvalidArgumentException('Tetapkan Company ID dan Property ID sebelum membuat snapshot pusat.');
        $revision = tamasyaMultiPropertyServerRevision($pdo);
        if ($revision === null) throw new RuntimeException('Revisi sumber tidak tersedia.');
        $finance = tamasyaCanonicalReportFinancial($pdo, $from, $to)['summary'];
        $trial = tamasyaMultiPropertyTrialBalance($pdo, $from, $to);
        $kpi = tamasyaGrowthOperationalKpis($pdo, $from, $to);
        $guard = tamasyaCanonicalReportIntegrity($pdo);
        $query = $pdo->prepare("SELECT COUNT(*) FROM historical_backfill_adjustments WHERE period_key BETWEEN LEFT(?,7) AND LEFT(?,7) AND review_status IN ('pending_review','pending_approval')");
        $query->execute([$from,$to]); $pending = (int)$query->fetchColumn();
        $conflicts = (int)$pdo->query("SELECT COUNT(*) FROM node_sync_conflicts WHERE status='open'")->fetchColumn();
        $map = ['revenue'=>'Pendapatan Operasional Diakui','expense'=>'Beban Operasional Diakui','profit'=>'Laba/Rugi Operasional','taxAccrued'=>'PBJT Terbentuk','taxPaid'=>'PBJT Dibayar','incomeTaxPaid'=>'PPh Dibayar','cashMovement'=>'Kas Bersih','bankMovement'=>'Bank/QRIS Bersih','liquidMovement'=>'Total Likuid Bersih'];
        $metrics = [];
        foreach ($map as $key=>$label) $metrics[$key] = tamasyaHybridMinor($finance[$label]);
        $metrics['journalDebit'] = tamasyaHybridMinor($trial['totalDebit']);
        $metrics['journalCredit'] = tamasyaHybridMinor($trial['totalCredit']);
        $metrics['roomRevenueEstimate'] = tamasyaHybridMinor($kpi['roomRevenue']);
        if($version==='tamasya-hq-snapshot-v3'){
            // Ledger balances are as of period end; payroll expense is the period movement.
            // These canonical accounts exist independently of optional Growth UI activation.
            $balances=$pdo->prepare("SELECT l.account_code,ROUND(SUM(l.debit-l.credit),2) balance FROM journal_entries e JOIN journal_lines l ON l.journal_entry_id=e.id WHERE e.status='posted' AND e.entry_date<=? AND l.account_code IN ('1103','1104','2103') GROUP BY l.account_code");
            $balances->execute([$to]);$byAccount=[];foreach($balances->fetchAll(PDO::FETCH_ASSOC) as $row)$byAccount[$row['account_code']]=$row['balance'];
            $metrics['guestReceivableBalance']=tamasyaHybridMinor($byAccount['1104']??0);
            $metrics['otaReceivableBalance']=tamasyaHybridMinor($byAccount['1103']??0);
            $metrics['accountsReceivableBalance']=(string)((int)$metrics['guestReceivableBalance']+(int)$metrics['otaReceivableBalance']);
            $metrics['accountsPayableBalance']=(string)(-(int)tamasyaHybridMinor($byAccount['2103']??0));
            $payroll=$pdo->prepare("SELECT COALESCE(ROUND(SUM(l.debit-l.credit),2),0) FROM journal_entries e JOIN journal_lines l ON l.journal_entry_id=e.id WHERE e.status='posted' AND e.entry_date BETWEEN ? AND ? AND l.account_code='5101'");
            $payroll->execute([$from,$to]);$metrics['payrollExpense']=tamasyaHybridMinor($payroll->fetchColumn());
        }
        $unresolved = (int)$finance['Transaksi Pajak Belum Diketahui'];
        $status = $trial['balanced'] ? $guard['status'] : 'FAIL';
        if (($unresolved || $pending || $conflicts) && $status === 'PASS') $status = 'WARNING';
        $result = ['contractVersion'=>$version,'companyId'=>$identity['companyId'],'propertyId'=>$identity['propertyId'],'propertyName'=>$identity['propertyName'],'currency'=>$identity['currency'],'timezone'=>$identity['timezone'],'period'=>['from'=>$from,'to'=>$to],'sourceRevision'=>$revision,'metricsMinor'=>$metrics,'roomNights'=>['sold'=>$kpi['soldRoomNights'],'available'=>$kpi['availableRoomNights']],'integrity'=>['status'=>$status,'unresolvedTaxCount'=>$unresolved,'pendingHistoricalCount'=>$pending,'openSyncConflicts'=>$conflicts]];
        $result['checksumSha256'] = tamasyaHybridChecksum($result);
        tamasyaHybridValidate($result);
        $pdo->commit();
        return $result;
    } catch (Throwable $error) {
        if ($pdo->inTransaction()) $pdo->rollBack();
        throw $error;
    }
}
