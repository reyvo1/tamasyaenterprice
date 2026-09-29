# RC2: aktivasi, pemulihan, dan hasil yang belum pasti

Status: final lokal / kandidat staging, 29 September 2026. Panduan ini tidak memberikan izin mengubah database produksi. Port/credential fixture tidak boleh dipakai sebagai konfigurasi produksi.

## Aktivasi bertahap

1. Verifikasi `FILE_CHECKSUMS.sha256`, simpan release sebelumnya, inventaris identitas company/property/node, schema, konfigurasi private dan feature flags. Pisahkan database properti dan read model HQ; verifikasi target sebelum installer.
2. Cadangkan database konsisten dan simpan log/PITR, konfigurasi private, kunci enkripsi, outbox/receipt serta konfigurasi cluster. Buktikan restore terisolasi. Dump SQL saja tidak membuktikan pemulihan seluruh sistem.
3. Untuk DB kosong, gunakan alur first-install/setup property. Jangan import `database_setup.sql` ke DB existing. Uji migrasi release lama pada salinan data dan gunakan jalur upgrade yang sesuai sebelum cutover.
4. Untuk modul optional, baca bantuan `optional_modules_install.php` dan panduan modul; gunakan backup yang benar-benar ada dengan `--backup-confirmed`, target yang dibutuhkan saja. Aktifkan feature flags/role setelah schema siap. Install/upgrade HQ memakai akun installer terpisah (`hq/install.php` untuk DB kosong; `hq/upgrade_h2.php` untuk upgrade yang didukung), lalu kembalikan runtime ke least privilege.
5. Runtime HQ membutuhkan SELECT/INSERT/UPDATE pada `hq_delivery_jobs` untuk delivery, selain grant read model terdokumentasi. Jangan memberi akses ledger hotel kepada HQ atau UPDATE/DELETE snapshot, receipt dan audit immutable. Worker tidak memakai kredensial installer.
6. Canary satu properti: login, identitas, shift, booking/payment exact cents, jurnal, pajak, snapshot v3 dan laporan HQ. Verifikasi satu writer, worker, receipt dan health sebelum menambah properti. Provider live tetap nonaktif sampai kontrak/credential/consent diuji dan diotorisasi.

## Mata uang dan transfer

Identitas currency database harus cocok dengan environment. Mengganti ENV bukan konversi saldo. Jangan mengedit currency data existing untuk melewati guard. Migrasi mata uang membutuhkan rancangan konversi/rekonsiliasi finance tersendiri. PO/invoice dengan mata uang berbeda ditolak sebelum posting. HQ memisahkan bucket currency tanpa mengarang FX.

Transfer memakai source leg, destination leg, lalu signed receipt/reconciliation. Timeout bukan bukti gagal: cocokkan operation ID, kedua status dan receipt sebelum retry. Jangan menyesuaikan saldo manual untuk menyamarkan pending leg. Lihat `INTERPROPERTY_TRANSFERS.md`.

## CRM dan delivery: sending/uncertain

UI Enterprise menyediakan **Tinjau penerima**. `sending` atau `uncertain` berarti hasil pengiriman belum pasti, bukan izin mengirim ulang. Cocokkan campaign/recipient/job/report ID, waktu, SMTP/provider log dan receipt. `blocked` perlu pemeriksaan consent/alamat. Snapshot ulang tidak boleh menghapus bukti atau menjadikan penerima terkirim eligible kembali.

Pengiriman ambigu ditahan, tidak otomatis diulang. Paket belum menyediakan tombol force-resend/reconciliation universal untuk semua provider. Simpan bukti, eskalasi ke operator berwenang dan tetapkan prosedur provider-specific sebelum menyelesaikan status. Jangan menghapus job, mengubah status lewat SQL atau membuat operation ID baru untuk memaksa retry.

## Rollback dan pemulihan

- Hentikan mutasi dengan prosedur maintenance teruji, hentikan worker, pastikan hanya satu writer. Rekam revisi/receipt terakhir dan antrean in-flight.
- Rollback kode hanya jika schema/data kompatibel; jangan downgrade schema destruktif otomatis.
- Restore bisa membuang transaksi/ACK sesudah backup. Arsipkan keadaan terkini, tentukan cutoff/PITR, cocokkan transaksi/receipt dengan sumber/provider. Jangan restore diam-diam lalu replay seluruh antrean.
- Setelah restore, periksa identitas, epoch/lease/fencing, checksum, jurnal, tax state dan idempotency receipts sebelum membuka mutasi. Jangan mempromosikan standby hanya karena UI primary tidak terjangkau.

## Gate produksi yang masih wajib

UAT hotel; build/start container dan FPM/nginx; domain/TLS/IAM; TLS DB nyata; partisi/failover lintas host dan DR terukur; kapasitas dataset realistis; provider/perangkat live; persetujuan RPO/RTO dan rekonsiliasi finance. Latency lokal bukan SLA. Simulasi tidak menutup semua fase PRD produksi.
