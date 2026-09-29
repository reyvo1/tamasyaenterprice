# Transfer bank antarproperti

Alur ini mencatat transfer bank yang sudah dilakukan dan menghubungkan dua jurnal hotel. Aplikasi tidak mengakses atau mengirim perintah ke bank. Transfer hanya antarproperti dalam perusahaan dan mata uang yang sama. Sumber dan penerima menjalankan canonical authority masing-masing; HQ tidak menjadi penulis uang.

## Aktivasi

1. Pasang build yang sama pada seluruh Primary/Standby. Buat dan verifikasi backup.
2. Jalankan `php optional_modules_install.php --apply --target=all --backup-confirmed=<referensi-backup>` pada database yang berwenang, lalu pastikan tabel `growth_interproperty_transfers` tercakup mirror dan checksum Standby.
3. Buat konfigurasi JSON private di luar document root pada setiap properti. Isi `companyId`, `propertyId`, dan `peers` sesuai identitas deployment. Setiap peer berisi `enabled: true` dan `secret` acak sekurangnya 32 karakter. Gunakan secret berbeda per pasangan properti. Kedua pihak suatu pasangan memakai secret yang sama.
4. Set `TAMASYA_INTERPROPERTY_KEYS_FILE` ke path private tersebut dan `TAMASYA_INTERPROPERTY_TRANSFER_ENABLED=1`. Restart PHP-FPM atau proses PHP agar environment terbaru berlaku. Jangan memublikasikan konfigurasi, menaruhnya di ZIP, atau memasukkannya ke source control.
5. Uji dengan rekening dan data staging. Akses menu Enterprise → Transfer antarproperti memerlukan role Admin/Manager/Finance dan hak menu Keuangan.

Contoh struktur tanpa secret nyata:

```json
{"companyId":"grup-contoh","propertyId":"hotel-a","peers":{"hotel-b":{"enabled":true,"secret":"GANTI_DENGAN_SECRET_ACAK_DARI_SECRET_MANAGER"}}}
```

Identitas database harus cocok dengan environment. Mengubah company/property/currency untuk database produksi bukan bagian aktivasi ini. Jangan mengubah mata uang atas data yang sudah diposting.

## Pengoperasian dan rekonsiliasi

- Petugas sumber mengonfirmasi dana sudah dikirim, memilih rekening, nominal, properti tujuan, dan referensi bank. Source mencatat debit Piutang Antarproperti (1198), kredit bank (1102), dengan status menunggu bukti penerima.
- Unduh dokumen sumber dari histori dan berikan melalui saluran operasional yang disetujui perusahaan. Dokumen memuat signature, identitas pasangan, nominal, mata uang, dan identitas transaksi sumber.
- Petugas penerima memastikan dana benar-benar masuk di bank, lalu mengimpor dokumen dengan rekening dan referensi bank penerima. Destination mencatat debit bank (1102), kredit Utang Antarproperti (2198). Unduh bukti penerimaan.
- Source mengimpor bukti penerimaan untuk mengubah status menjadi cocok/reconciled. Rekonsiliasi tidak membuat transaksi uang baru. Referensi, nominal, currency, pasangan, fingerprint sumber, dan signature harus sesuai.
- Bukti dan transaksi yang telah diposting dipertahankan. Transfer tidak menjadi pendapatan/beban operasional atau objek PBJT dalam classifier canonical. Saldo antarproperti 1198/2198 harus direkonsiliasi dalam penutupan buku perusahaan; tidak ada eliminasi otomatis hanya berdasarkan kesamaan nominal.

## Gangguan koneksi dan koreksi

Browser menyimpan operation ID sebelum pengiriman. Jika jawaban belum pasti, gunakan permintaan tersimpan dan periksa histori; jangan membuat operation ID atau referensi baru untuk transfer fisik yang sama. Salinan dokumen/bukti dapat diunduh lagi dari histori. Destination menolak isi berbeda untuk transfer ID yang sama; transaksi dan referensi bank mempunyai batas unik untuk mencegah pencatatan ulang.

Jangan mengganti secret pasangan selama masih ada transfer menunggu bukti. Simpan backup private konfigurasi bersama prosedur pemulihan; kehilangan key membuat verifikasi dokumen lama tidak tersedia. Rotasi dilakukan setelah seluruh dokumen dengan key lama direkonsiliasi.

Tidak ada pembatalan lintas hotel secara otomatis: sumber tidak dapat mengasumsikan penerima belum mencatat uang. Dana yang dikembalikan dicatat sebagai transfer bank baru arah sebaliknya dengan referensi bank pengembalian, lalu direkonsiliasi menggunakan alur yang sama. Nilai negatif dan perubahan histori transaksi tidak digunakan untuk membatalkan transfer.

## Batas bukti

Simulasi lokal dua database menguji paired legs, replay, signature/scope mismatch, rekonsiliasi, kas/bank, pajak, dan jurnal. Transfer bank nyata, prosedur otorisasi perusahaan, kegagalan dua mesin, DR dan UAT pengguna masih memerlukan lingkungan target. Tidak ada instruksi dalam panduan ini yang menyatakan server produksi sudah tersedia atau sudah diterapkan.
