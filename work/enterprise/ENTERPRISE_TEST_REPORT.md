# TAMASYA Enterprise RC2 — hasil final lokal

Dikemas 30 September 2026; integrasi diuji 29 September 2026 di Ubuntu/Linux, PHP 8.5.4, MySQL 8.4.11 dan Node 22.23.3. Kelanjutan proyek yang dipindahkan dari Windows, bukan pembangunan ulang.

**895 pemeriksaan integrasi/artefak + 194 assertion unit lulus (1089 total), nol gagal pada hasil final yang disertakan. Final lokal / kandidat staging, belum deployment atau sertifikasi produksi.** Hasil percobaan gagal sebelum koreksi harness tidak dihitung sebagai hasil final.

## Yang diverifikasi

- Fresh extracted candidate: database kosong, first-install, setup READY, core booking/finance/POS, split/refund, backfill, shift locking, konkurensi, alokasi, pajak, jurnal, ekspor dan restore. Dataset synthetic; tidak menyentuh database sistem atau datadir lama pengguna.
- Growth/Enterprise: procurement/GRN/AP, folio/rates/groups/corporate, CRM consent/loyalty, durable recipient claim dan ambiguous delivery, payment foundation, payroll exact cents. HQ v3 payroll/AR/AP berasal dari jurnal canonical; v2 kompatibel, laporan frozen tetap immutable dan coverage mixed-version eksplisit.
- USD: currency dokumen mengikuti properti, pembayaran 12.34 tetap presisi, posting GRN/PO serta invoice mismatch ditolak, perubahan deployment currency ditolak tanpa mengubah saldo existing. Ini bukan implementasi konversi mata uang.
- Transfer antarproperti: dua DB, dua leg canonical, signed receipt, replay/conflict/reconciliation, jurnal seimbang dan net bank perusahaan nol tanpa mengarang revenue/expense/tax.
- HQ dua properti, tenant scope dan least privilege; worker concurrency/restart/backoff/DLQ/ACK; laporan/realtime; delivery dan storage HTTPS simulator. Tidak ada pesan atau transaksi dikirim ke provider/penerima nyata.
- HA: dua proses PHP dan dua DB lokal, mirror data core/optional, stale-row removal, checksum, planned switch satu writer dan commit fencing. Ini bukan bukti failover lintas mesin/fault domain.
- Perbaikan PHP 8.5 HTTP headers/CurlHandle serta cache navigasi Enterprise memiliki pemeriksaan regresi. Harness Windows dipindahkan ke Linux, tanpa mengubah data lama.

## Hasil per suite

| Suite | Lulus | Gagal |
|---|---:|---:|
| setup | 23 | 0 |
| core | 22 | 0 |
| finance | 24 | 0 |
| operations | 21 | 0 |
| concurrency | 5 | 0 |
| shift-lock | 1 | 0 |
| extended-finance | 50 | 0 |
| allocation | 21 | 0 |
| settlement-sync | 21 | 0 |
| finance-controls | 22 | 0 |
| accounting-report | 35 | 0 |
| tax-edge | 12 | 0 |
| shift-integrity | 16 | 0 |
| report-export | 51 | 0 |
| restore | 8 | 0 |
| hybrid | 59 | 0 |
| hybrid-failure | 26 | 0 |
| hybrid-pagination | 3 | 0 |
| hq-permission | 7 | 0 |
| second-property | 20 | 0 |
| control | 20 | 0 |
| enterprise-worker | 7 | 0 |
| enterprise-report | 24 | 0 |
| delivery | 18 | 0 |
| object-storage | 7 | 0 |
| ha-commit | 24 | 0 |
| ha-pair | 16 | 0 |
| deployment | 9 | 0 |
| growth-procurement | 46 | 0 |
| growth-folio-rate | 20 | 0 |
| growth-crm | 32 | 0 |
| growth-crm-delivery | 31 | 0 |
| growth-payment | 27 | 0 |
| growth-payroll | 24 | 0 |
| growth-group | 33 | 0 |
| growth-hq-v3 | 19 | 0 |
| provider-bridge | 15 | 0 |
| growth-currency | 44 | 0 |
| growth-interproperty | 32 | 0 |

Unit: regression.php (44), regression.mjs (12), finance-regression.php (9), hybrid-regression.php (33), hq-v3-regression.php (11), growth-input-regression.php (19), provider-bridge-regression.php (27), realtime-regression.mjs (16), device-contract-regression.php (9), database-tls-regression.php (4), growth-failover-regression.mjs (10).

## Kinerja lokal dan batas pembuktian

Snapshot canonical: 40 request, concurrency 4, 2 proses PHP development; p50 420.4 ms, p95 743.46 ms, maksimum 896.61 ms. Bukan SLA PHP-FPM/produksi.

- `server-revision`: 12 request berurutan, p50 41.2 ms, p95 75.64 ms; ETag hadir: False.
- `hotel-data`: 12 request berurutan, p50 158.72 ms, p95 178.83 ms; ETag hadir: False.


Kedua endpoint read tersebut tidak mengirim ETag pada pengukuran ini, sehingga biaya conditional read tidak diklaim terukur. Authorized ETag 304 HQ diuji dalam suite hybrid. Sampel kecil/dataset synthetic tidak membuktikan p95 seluruh interaksi atau kapasitas target.

Tes transaksi dilakukan melalui API otomatis, bukan semua formulir diklik manual. Ekspor diuji struktur/angka/checksum, bukan review visual setiap halaman. Compose/YAML/provisioning diuji statis; container/FPM/nginx belum dijalankan pada target. TLS DB memiliki tes konfigurasi, bukan koneksi positif ke endpoint produksi.

Masih perlu UAT hotel, akses server target, domain/TLS/IAM, provider/perangkat live, load representatif, quorum/fencing lintas host, network partition, unplanned failover, PITR/DR serta RPO/RTO terukur. FX/eliminasi intercompany khusus dan prosedur reconciliation provider-specific tidak diasumsikan tersedia. Jangan menafsirkan hasil lokal sebagai semua fase PRD selesai produksi.

## Artefak dan keselamatan

Paket `TAMASYA-ENTERPRISE-RC2-2026-09-30.zip` berisi source serta `FILE_CHECKSUMS.sha256`. Baca `ENTERPRISE_IMPLEMENTATION_STATUS.md` dan `deploy/RC2_ACTIVATION_RECOVERY.md`. SQL fresh hanya untuk DB kosong; upgrade existing memerlukan backup/restore teruji serta jalur migrasi yang sesuai.

Runtime dibandingkan byte dengan kandidat yang diuji; perubahan setelah integrasi hanya literal build/cache ID 20260923 → 20260929 serta dokumentasi/manifest. ZIP final diekstrak kembali, checksum dan seluruh lint/reference diperiksa, lalu semua 194 assertion unit dijalankan kembali. Rincian final terdapat pada JSON hasil dan bukti pengujian.

Bukti yang dibagikan hanya nama assertion/status, laporan statis dan unit, metrik lokal serta source harness tanpa konfigurasi private. Credential, session/token, dump database, private key, outbox dan raw log fixture tidak disertakan. Artefak RC1 lama tetap dipertahankan.
