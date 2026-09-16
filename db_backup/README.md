# Old backups

`backup.sql` and `backup.dump` are from 18 February 2026, taken from the AWS
RDS database this app used before it moved to Neon. They cover six of the
seventeen tables — no training data at all, and about half the symptom log.
Kept because they are the only record of that era, not because they are a
backup of anything current.

The scripts that made them have been removed. They pointed at the RDS host,
which no longer exists, so they failed every time they ran and left a
zero-byte file behind — which is worse than having no script, because it is
why the backups looked healthy.

What replaces them:

- `backend/scripts/backup_db.py` — dumps every table, reading through raw SQL
  so the Fernet-encrypted columns stay encrypted in the file.
- `backend/scripts/restore_db.py` — puts one back, into a database you name.
  It refuses to write into a database that already holds rows.
- `deploy/fbc-backup.timer` — runs it nightly on the server, keeping 30 days.
- `deploy/pull_backups.sh` — copies them to your own machine.

**FERNET_KEY**, from the server's `.env`, is required to read any of it. Keep a
copy somewhere safe and somewhere separate from the dumps.
