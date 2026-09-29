# Payment / channel bridge v1

Provider belum dipilih. Kontrak ini adalah batas integrasi provider-neutral dan validasi sandbox, bukan bukti integrasi vendor atau penerimaan pembayaran. Canonical PHP tetap satu-satunya penulis booking, pembayaran, jurnal, pajak dan shift.

## Envelope

JSON memiliki tepat `version`, `body`, `signature`. Version adalah `tamasya-provider-bridge-v1`. Body adalah base64 standar dari byte UTF-8 JSON (maksimum 65.536 karakter base64). Signature adalah hex lowercase HMAC-SHA256 atas `tamasya-provider-bridge-v1` + newline LF + body base64, memakai secret minimal 32 byte. Secret hanya direferensikan sebagai `env:VARIABLE`; jangan disimpan dalam config JSON, log atau paket distribusi.

Body memiliki tepat companyId, propertyId, providerCode, adapterType, eventId, issuedAt, expiresAt, currency, eventType, payload. Identity/currency wajib cocok dengan properti dan adapter tujuan. Timestamp integer Unix UTC, berlaku maksimum 300 detik, toleransi waktu maju 30 detik. Redelivery mempertahankan eventId dan payload, tetapi membuat issuedAt/expiresAt/signature baru. Jam kedua sisi harus tersinkron.

Payment: adapterType `payment`, eventType `payment.status`, payload tepat `intentId`, `status` (pending/paid/failed/cancelled), `amountMinor` integer positif. Minor unit di kontrak internal TAMASYA ini selalu 1/100 currency, termasuk IDR. Adapter vendor wajib mengonversi unit vendor secara eksplisit dan menolak pembulatan ambigu.

Channel: adapterType `channel`, eventType reservation.created/reservation.updated/reservation.cancelled. Payload tepat externalReservationId, externalRoomType, checkIn, checkOut (tanggal kalender YYYY-MM-DD, checkout sesudah checkin), totalMinor integer nonnegatif. Event cancellation tetap membawa snapshot masa inap dan nominal. Tidak membawa PII tamu pada versi kontrak ini.

## Validasi lokal

Admin dengan akses konfigurasi memakai authenticated POST `api.php?action=enterprise-suite`, command `provider-bridge-validate`, operationId, adapterId, envelope. Enterprise/adapters harus aktif, adapter mode sandbox dan verifier hmac_sha256/sha256_hmac. CSRF/origin, auth dan writer guard aplikasi tetap berlaku. Ini bukan endpoint webhook publik.

HTTP 200 dengan `status=validated_only`, `durablyAccepted=false` hanya menyatakan validasi berhasil. Jangan menganggapnya ACK penerimaan event. HMAC membuktikan kepemilikan key bridge; `providerSignatureVerified=false` karena signature vendor belum diimplementasikan. Validasi tidak menyimpan event, mengirim network request, membuat booking atau membukukan uang.

`eventKey` mengidentifikasi company/property/provider/type/eventId; `contentHash` mencakup seluruh isi bisnis dengan urutan field stabil, tanpa timestamp transport. Receiver durable kelak wajib menyimpan key+hash dalam transaksi dengan unique key. Event key sama/hash sama mengembalikan receipt lama; key sama/hash berbeda ditolak sebagai conflict. ACK accepted hanya boleh dikirim setelah commit durable. Timeout berarti uncertain; pengirim mengulang event yang sama, bukan membuat event ID baru. Signature tetap diverifikasi pada setiap retry.

Simulasi lokal memakai SQLite inbox sementara untuk membuktikan urutan commit/ACK, lost ACK, restart koneksi, duplicate dan conflict. Itu fixture pengujian, bukan penyimpanan produksi. Database produksi belum memiliki receiver bridge durable otomatis.

## Gate adapter vendor

Setelah vendor dipilih: implementasikan verifikasi signature dan event mapping vendor, simpan receipt durable pada DB properti, cocokkan intent+nominal+currency, pastikan reversal/chargeback mengikuti otoritas canonical, dan uji settlement di sandbox vendor. OTA membutuhkan pemetaan room/rate, availability dan konflik pembaruan reservasi sebelum boleh mengubah booking. Event paid tidak boleh langsung dianggap uang masuk tanpa rekonsiliasi yang tepat. Migrasi ke production harus melalui pengujian vendor dan staging, bukan mengganti mode saja.

Untuk dua server, receiver durable harus berada dalam data yang direplikasi dan commit memakai fencing writer yang sama. Standby tidak boleh menjadi penulis kedua saat koneksi putus. Simulasi pada satu komputer tidak membuktikan HA lintas server atau network partition.
