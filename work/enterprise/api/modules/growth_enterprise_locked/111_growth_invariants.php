<?php
declare(strict_types=1);
if (!defined('TAMASYA_API_ENTRY')) { http_response_code(404); exit; }

/** Serialize receipt/invoice consumption on the common PO, including sibling drafts. */
function tamasyaEnterpriseLockPurchaseOrder(PDO $pdo,string $id): array {
    if(!$pdo->inTransaction())throw new RuntimeException('Purchase order validation requires a transaction.');
    $q=$pdo->prepare('SELECT * FROM growth_purchase_orders WHERE id=? FOR UPDATE');$q->execute([$id]);$po=$q->fetch(PDO::FETCH_ASSOC);
    if(!$po||!in_array($po['status'],['approved','received'],true))throw new RuntimeException('PO harus approved/received dan belum cancelled/closed.');
    if(($po['currency']??'')!==tamasyaMultiPropertyIdentity()['currency'])throw new RuntimeException('Mata uang PO berbeda dari properti; rekonsiliasi dokumen dahulu.');
    return $po;
}

function tamasyaEnterpriseValidateReceiptPosting(PDO $pdo,array $receipt): void {
    tamasyaEnterpriseLockPurchaseOrder($pdo,(string)$receipt['po_id']);
    $q=$pdo->prepare('SELECT po_item_id,quantity_received FROM growth_goods_receipt_items WHERE grn_id=? AND stock_applied=0 ORDER BY po_item_id,id FOR UPDATE');$q->execute([$receipt['id']]);$requested=[];
    foreach($q->fetchAll(PDO::FETCH_ASSOC) as $row){$qty=(int)round((float)$row['quantity_received']*1000);if($qty<=0)throw new RuntimeException('Quantity GRN wajib positif.');$requested[$row['po_item_id']]=($requested[$row['po_item_id']]??0)+$qty;}
    if(!$requested)throw new RuntimeException('GRN tidak memiliki item untuk diposting.');
    foreach($requested as $id=>$qty){
        $q=$pdo->prepare('SELECT quantity,received_quantity FROM growth_purchase_order_items WHERE id=? AND po_id=? FOR UPDATE');$q->execute([$id,$receipt['po_id']]);$item=$q->fetch(PDO::FETCH_ASSOC);
        if(!$item||$qty>(int)round(((float)$item['quantity']-(float)$item['received_quantity'])*1000))throw new RuntimeException('Penerimaan melebihi sisa PO terkini; perbarui draft GRN.');
    }
}

function tamasyaEnterpriseValidateInvoiceCapacity(PDO $pdo,array $invoice): void {
    if(($invoice['currency']??'')!==tamasyaMultiPropertyIdentity()['currency'])throw new RuntimeException('Mata uang invoice berbeda dari properti.');
    if(empty($invoice['po_id']))return;
    $po=tamasyaEnterpriseLockPurchaseOrder($pdo,(string)$invoice['po_id']);
    if((string)$po['vendor_id']!==(string)$invoice['vendor_id'])throw new RuntimeException('Vendor invoice berbeda dari PO.');
    $q=$pdo->prepare('SELECT po_item_id,SUM(quantity) quantity FROM growth_supplier_invoice_lines WHERE supplier_invoice_id=? GROUP BY po_item_id ORDER BY po_item_id');$q->execute([$invoice['id']]);
    foreach($q->fetchAll(PDO::FETCH_ASSOC) as $line){
        $id=$line['po_item_id'];if(!$id)throw new RuntimeException('Invoice PO wajib menunjuk item PO.');
        $s=$pdo->prepare('SELECT quantity FROM growth_purchase_order_items WHERE id=? AND po_id=? FOR UPDATE');$s->execute([$id,$invoice['po_id']]);$capacity=$s->fetchColumn();if($capacity===false)throw new RuntimeException('Item invoice bukan milik PO.');
        $used=$pdo->prepare("SELECT COALESCE(SUM(l.quantity),0) FROM growth_supplier_invoice_lines l JOIN growth_supplier_invoices i ON i.id=l.supplier_invoice_id WHERE l.po_item_id=? AND i.id<>? AND i.status IN ('posted','partially_paid','paid')");$used->execute([$id,$invoice['id']]);
        if((int)round(((float)$used->fetchColumn()+(float)$line['quantity'])*1000)>(int)round((float)$capacity*1000))throw new RuntimeException('Akumulasi invoice melebihi quantity PO.');
        if(!empty($invoice['grn_id'])){
            $s=$pdo->prepare("SELECT COALESCE(SUM(g.quantity_received),0) FROM growth_goods_receipt_items g JOIN growth_goods_receipts r ON r.id=g.grn_id WHERE g.grn_id=? AND g.po_item_id=? AND r.po_id=? AND r.status='posted'");$s->execute([$invoice['grn_id'],$id,$invoice['po_id']]);$received=(float)$s->fetchColumn();
            $used=$pdo->prepare("SELECT COALESCE(SUM(l.quantity),0) FROM growth_supplier_invoice_lines l JOIN growth_supplier_invoices i ON i.id=l.supplier_invoice_id WHERE l.po_item_id=? AND i.grn_id=? AND i.id<>? AND i.status IN ('posted','partially_paid','paid')");$used->execute([$id,$invoice['grn_id'],$invoice['id']]);
            if((int)round(((float)$used->fetchColumn()+(float)$line['quantity'])*1000)>(int)round($received*1000))throw new RuntimeException('Akumulasi invoice melebihi quantity GRN.');
        }
    }
}

/** One projection for legacy links and AP settlement; never count the same payment twice. */
function tamasyaEnterprisePoPaymentSql(PDO $pdo):string{
    $sql="SELECT po_id,transaction_id,SUM(amount_applied) amount_applied FROM growth_purchase_order_payments GROUP BY po_id,transaction_id";
    if(tamasyaGrowthTableExists($pdo,'growth_supplier_invoice_payments'))
        $sql.=" UNION ALL SELECT i.po_id,p.transaction_id,SUM(p.amount_applied) amount_applied FROM growth_supplier_invoice_payments p JOIN growth_supplier_invoices i ON i.id=p.supplier_invoice_id WHERE i.po_id IS NOT NULL AND i.status IN ('posted','partially_paid','paid') GROUP BY i.po_id,p.transaction_id";
    return 'SELECT a.po_id,a.transaction_id,MAX(a.amount_applied) amount_applied FROM ('.$sql.') a JOIN transactions t ON t.id=a.transaction_id GROUP BY a.po_id,a.transaction_id';
}
function tamasyaEnterprisePurchaseOrderPaid(PDO $pdo,string $poId):float{
    $q=$pdo->prepare('SELECT COALESCE(SUM(amount_applied),0) FROM ('.tamasyaEnterprisePoPaymentSql($pdo).') p WHERE p.po_id=?');$q->execute([$poId]);return (float)$q->fetchColumn();
}
function tamasyaEnterpriseAssertLegacyPoPayment(PDO $pdo,array $tx):void{
    $sem=tamasyaTransactionSemantics($tx);
    if(!$sem['isLiquidExternalExpense']||$sem['isRevenueRefund']||$sem['isPbjtSettlement']||$sem['isIncomeTaxSettlement']||$sem['isOpeningBalance']||str_contains($sem['kind'],'salary')||($tx['categorySystemKey']??'')==='payroll_expense'||in_array($sem['kind'],['supplier_ap_payment','refund','pos_refund','security_deposit_refund','interproperty_transfer_out'],true))
        throw new InvalidArgumentException('Pilih pembayaran pemasok liquid yang belum ditautkan melalui AP.');
    if(tamasyaGrowthTableExists($pdo,'growth_supplier_invoice_payments')){
        $q=$pdo->prepare('SELECT id FROM growth_supplier_invoice_payments WHERE transaction_id=? LIMIT 1');$q->execute([$tx['id']]);
        if($q->fetchColumn())throw new InvalidArgumentException('Pembayaran AP telah dialokasikan otomatis ke invoice/PO.');
    }
}

function tamasyaEnterpriseValidatePoTransition(PDO $pdo,array $po,string $target): void {
    if(!tamasyaEnterpriseEnabled()||!tamasyaEnterpriseModuleEnabled('ap'))return;
    $q=$pdo->prepare('SELECT quantity,received_quantity FROM growth_purchase_order_items WHERE po_id=? ORDER BY id FOR UPDATE');$q->execute([$po['id']]);$items=$q->fetchAll(PDO::FETCH_ASSOC);
    if($target==='received')foreach($items as $item)if((int)round((float)$item['received_quantity']*1000)<(int)round((float)$item['quantity']*1000))throw new RuntimeException('Posting GRN seluruh item dahulu sebelum menandai PO received.');
    if($target==='cancelled'){
        foreach($items as $item)if((float)$item['received_quantity']>0)throw new RuntimeException('PO yang sudah menerima barang tidak boleh dibatalkan.');
        if(tamasyaEnterprisePurchaseOrderPaid($pdo,(string)$po['id'])>0)throw new RuntimeException('PO yang telah dibayar tidak boleh dibatalkan.');
        $q=$pdo->prepare("SELECT COUNT(*) FROM growth_supplier_invoices WHERE po_id=? AND status IN ('posted','partially_paid','paid')");$q->execute([$po['id']]);if((int)$q->fetchColumn()>0)throw new RuntimeException('PO dengan invoice posted tidak boleh dibatalkan.');
    }
}

/** Keep the scope behind allocated corporate/master folios stable. */
function tamasyaEnterpriseAssertGroupBookingUnlinkable(PDO $pdo,string $bookingId): void {
    $q=$pdo->prepare('SELECT id FROM bookings WHERE id=? FOR UPDATE');$q->execute([$bookingId]);
    if(!tamasyaGrowthTableExists($pdo,'growth_folios'))return;
    $q=$pdo->prepare("SELECT a.id FROM growth_folio_charge_allocations a JOIN growth_folios f ON f.id=a.folio_id WHERE a.booking_id=? AND f.folio_type IN ('master','company') LIMIT 1 FOR UPDATE");$q->execute([$bookingId]);
    if($q->fetchColumn())throw new RuntimeException('Lepas alokasi tagihan folio master/corporate sebelum mengubah keanggotaan group. Invoice aktif harus di-void melalui alur audit.');
    $q=$pdo->prepare("SELECT a.id FROM growth_folio_transaction_allocations a JOIN growth_folios f ON f.id=a.folio_id JOIN transactions t ON t.id=a.transaction_id WHERE t.bookingId=? AND f.folio_type IN ('master','company') LIMIT 1 FOR UPDATE");$q->execute([$bookingId]);
    if($q->fetchColumn())throw new RuntimeException('Lepas alokasi pembayaran folio master/corporate sebelum mengubah keanggotaan group.');
}

function tamasyaEnterpriseValidateRouteScope(PDO $pdo,array $folio,string $bookingId,string $groupId):void{
    if(($bookingId==='')===($groupId===''))throw new InvalidArgumentException('Pilih tepat satu scope routing: booking atau group.');
    if($folio['status']!=='open')throw new InvalidArgumentException('Folio routing harus open.');
    if($bookingId!==''){
        $q=$pdo->prepare('SELECT id FROM bookings WHERE id=? FOR UPDATE');$q->execute([$bookingId]);
        if(!$q->fetchColumn()||!in_array($bookingId,tamasyaEnterpriseFolioEligibleBookingIds($pdo,$folio),true))throw new InvalidArgumentException('Booking di luar scope folio tujuan.');
        return;
    }
    $q=$pdo->prepare('SELECT company_id FROM growth_group_reservations WHERE id=? FOR UPDATE');$q->execute([$groupId]);$group=$q->fetch(PDO::FETCH_ASSOC);
    if(!$group||!empty($folio['booking_id']))throw new InvalidArgumentException('Group tidak cocok dengan folio tujuan.');
    if(!empty($folio['group_id'])){
        if($folio['group_id']!==$groupId)throw new InvalidArgumentException('Group di luar scope folio tujuan.');
    }elseif(empty($folio['company_id'])||$folio['company_id']!==$group['company_id'])throw new InvalidArgumentException('Perusahaan group berbeda dari folio tujuan.');
}

function tamasyaEnterpriseAssertFolioPayment(array $tx): void {
    $kind=strtolower((string)($tx['transactionKind']??'manual'));
    $bank=strtolower((string)($tx['bankAccountId']??''));$type=(string)($tx['type']??'');
    if(in_array($bank,['inventory_asset','guest_receivable','accounts_payable'],true)
        ||in_array($kind,['security_deposit_received','security_deposit_refund','security_deposit_forfeit','pos_cogs','pos_cogs_reversal','pos_room_charge','supplier_invoice_accrual','supplier_inventory_accrual','supplier_asset_accrual','supplier_ap_payment','internal_transfer','ota_transfer'],true)
        ||!($type==='income'||($type==='expense'&&$kind==='refund')))
        throw new RuntimeException('Transaksi bukan pembayaran/refund booking yang dapat dialokasikan ke folio.');
}

function tamasyaGrowthValidateRawInput(string $command,array $input):void{
    $number=static function($value,string $field,bool $positive=false,?float $max=null):void{
        if(is_bool($value)||!is_scalar($value)||!is_numeric($value)||!is_finite((float)$value)||(float)$value<0||($positive&&(float)$value<=0)||(float)$value>($max??9999999999999.99))throw new InvalidArgumentException('Nilai '.$field.' tidak valid.');
    };
    foreach(['taxRate','routePercent','routedPercent','percent'] as $field)if(array_key_exists($field,$input))$number($input[$field],$field,in_array($field,['routePercent','percent'],true),100);
    foreach(['pointsPer1000','creditLimit','paymentTermsDays','roomBlockQty','minStay','priority'] as $field)if(array_key_exists($field,$input))$number($input[$field],$field);
    if(in_array($command,['pr-save','grn-save','po-save','supplier-invoice-save'],true)){
        $field=$command==='supplier-invoice-save'?'lines':'items';$items=$input[$field]??null;
        if(!is_array($items)||!array_is_list($items)||count($items)<1||count($items)>500)throw new InvalidArgumentException('Daftar item wajib berisi 1 sampai 500 item.');
        foreach($items as $item){
            if(!is_array($item))throw new InvalidArgumentException('Format item tidak valid.');
            foreach(['quantity','quantityReceived','estimatedUnitPrice','unitPrice','taxRate'] as $name)if(array_key_exists($name,$item))$number($item[$name],$name,in_array($name,['quantity','quantityReceived'],true),$name==='taxRate'?100:null);
            if(isset($item['accountClass'])&&!in_array($item['accountClass'],['expense','inventory','asset'],true))throw new InvalidArgumentException('Kelas akun item tidak dikenal.');
        }
    }
}
function tamasyaEnterpriseValidateSegmentCondition(array $condition):void{
    foreach($condition as $key=>$value){
        if(!in_array($key,['tier_in','min_lifetime_spend','min_nights','email_required'],true))throw new InvalidArgumentException('Kondisi segment tidak dikenal.');
        if($key==='email_required'&&!is_bool($value))throw new InvalidArgumentException('email_required wajib boolean.');
        if($key==='tier_in'&&(!is_array($value)||!array_is_list($value)||!$value||array_diff($value,['member','silver','gold','platinum'])))throw new InvalidArgumentException('Daftar tier segment tidak valid.');
        if(in_array($key,['min_lifetime_spend','min_nights'],true)&&(is_bool($value)||!is_scalar($value)||!is_numeric($value)||!is_finite((float)$value)||(float)$value<0))throw new InvalidArgumentException('Batas segment tidak valid.');
    }
}
