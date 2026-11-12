# Monitoring Jobdesk Harian

Email harian + pengingat deadline (H-2, H-1, hari H, terlambat) via GitHub Actions.

## Setup (sekali saja)
1. Buat repo **private** di GitHub, upload semua file ini.
2. Buat *App Password* Gmail: Akun Google > Keamanan > Verifikasi 2 langkah > Sandi aplikasi.
3. Repo > Settings > Secrets and variables > Actions > New repository secret:
   - `SMTP_USER` : alamat Gmail pengirim
   - `SMTP_PASS` : app password 16 karakter
   - `MAIL_TO`    : email Anda (penerima ringkasan harian & CC pengingat)
4. Tab Actions > *Daily Jobdesk Monitor* > Run workflow (centang dry run dulu untuk tes).

## Pemakaian harian
Edit `tasks.csv` langsung di GitHub (ikon pensil), lalu commit.

| Kolom | Isi |
|---|---|
| id | nomor urut |
| jobdesk | nama tugas |
| pic / email_pic | penanggung jawab & emailnya (kosong = pengingat dikirim ke MAIL_TO) |
| prioritas | Tinggi / Sedang / Rendah |
| deadline | format `YYYY-MM-DD` |
| status | Belum / Proses / Selesai / Ditunda |
| catatan | bebas |

## Aturan notifikasi
- Ringkasan harian selalu dikirim jam 08:00 WIB.
- Pengingat ke PIC dikirim untuk status aktif dengan sisa waktu <= `REMINDER_DAYS` (default 2) sampai terlambat, setiap hari sampai status diubah ke `Selesai`.
- Status `Ditunda` tidak memicu pengingat.
- Ubah jadwal di `cron`, ubah ambang H-n di `REMINDER_DAYS` pada file workflow.
