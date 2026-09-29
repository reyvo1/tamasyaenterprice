# TAMASYA Enterprise RC2 — status implementasi

29 September 2026. Kelanjutan proyek Windows yang dipulihkan ke Ubuntu, bukan pembangunan ulang. RC2 diuji dengan PHP 8.5.4/MySQL 8.4.11 pada fixture baru terisolasi. **Final lokal / kandidat staging, bukan sertifikasi siap produksi.** Laporan pengujian RC2 menjadi acuan; dokumen RC1/H1/R4 adalah histori baseline.

## Penambahan RC2 dan traceability PRD

| Area | Implementasi/bukti lokal | Batas |
|---|---|---|
| PRD §5.3 payroll/AR/AP | Snapshot v3 dari jurnal canonical, kompatibilitas v2, coverage versi campuran, laporan beku immutable | FX/eliminasi intercompany khusus tidak diasumsikan |
| PRD §5.3 transfer | Dua leg canonical, signed destination receipt, retry idempotent, rekonsiliasi dua DB | Rekonsiliasi bank nyata perlu UAT finance |
| Growth/Enterprise | Procurement/GRN/AP, rate/folio/group/corporate, payment foundation, CRM consent/loyalty/delivery, payroll exact cents dan lifecycle guards | Semua variasi formulir tetap perlu UAT pengguna |
| Mata uang | USD fixture dan guard mismatch dokumen/deployment; HQ memisahkan mata uang | Mengganti ENV bukan konversi saldo |
| PRD §7 | Failover read, mutasi ambigu tidak diulang otomatis, mirror tabel optional dengan penghapusan stale rows | Matriks offline perangkat nyata dan partisi lintas mesin belum dibuktikan |

Perbaikan pemulihan OS mencakup HTTP headers/CurlHandle PHP 8.5, harness lintas OS, dan cache navigasi Enterprise pada service worker. Build/cache ID diperbarui tanpa mengubah kontrak schema core. Baca `deploy/RC2_ACTIVATION_RECOVERY.md` sebelum aktivasi.

## Fondasi Enterprise yang dipertahankan

| Bagian | Implementasi dan bukti lokal | Gate yang belum tertutup |
|---|---|---|
| Core keuangan/operasional | PHP canonical tetap menjadi penulis transaksi; suite transaksi normal, backfill, jurnal, pajak, shift, laporan, replay dan restore | UAT data serta prosedur hotel target |
| Isolasi dan administrasi tenant | Database hotel terpisah, HQ read model, registry perusahaan/properti, role/grant/revoke/suspend, audit immutable, provisioning private | Routing/domain dan provisioning di infrastruktur target |
| Laporan Enterprise | Snapshot immutable, sumber/revisi/checksum, rekonsiliasi dan ekspor JSON/CSV/XLSX/PDF/email/Telegram | Review visual semua variasi laporan; kebijakan konsolidasi khusus perusahaan |
| Async | Worker opsional, outbox immutable, ACK, backoff, DLQ, lock dan restart; pengiriman laporan melalui bridge | Provider email/Telegram nyata dan rekonsiliasi operasional uncertain delivery |
| Realtime/IoT | SSE bertiket, expiry/scope, revision-only, fallback polling; worker perangkat dengan ACK job spesifik | Bridge/perangkat fisik dan kapasitas koneksi target |
| HA hybrid | Dua proses PHP + dua database lokal, mirror, checksum, planned switch dan satu writer; commit fencing epoch/lease/token | Kegagalan mesin/jaringan lintas fault domain, pemulihan primary lama dan DR |
| SaaS deployment | Profil PHP-FPM/Nginx, beberapa API, HQ/realtime/worker, single-writer DB endpoint, TLS DB opsional, private object storage SigV4 | Build/start container, DB quorum/Router/provider, IAM/S3 nyata, autoscaling dan DR |
| Kapasitas | Baseline beban lokal dicatat terpisah; tanpa klaim SLA | Load test representatif di PHP-FPM dan sizing host/database |

Database-per-property meneruskan isolasi yang sudah ada pada aplikasi awal. Ini bukan migrasi diam-diam menuju tabel multi-tenant bersama. Feature opsional tetap dapat dinonaktifkan tanpa mengganti jalur akuntansi/pajak core.

Paket tidak menyediakan server, kredensial cloud, provider pesan, atau perangkat fisik. Gate fase 4–6 PRD mensyaratkan load/failover/DR pada target; konfigurasi dan simulasi lokal tidak menggantikan gate tersebut. Jangan mengubah status ini menjadi “seluruh PRD selesai produksi” hanya karena seluruh pemeriksaan lokal lulus.

Lihat `deploy/README.md` untuk deployment dan `ENTERPRISE_TEST_REPORT.md` untuk angka, batas uji, serta berkas bukti hasil akhir.
