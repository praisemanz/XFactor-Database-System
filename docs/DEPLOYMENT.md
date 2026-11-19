# Publishing online (extra credit 7c)

The web app goes on **Render** (free web service) and the database on **Aiven for MySQL** (free plan).
Both have free tiers, and Aiven runs real MySQL 8, so the views and stored procedures work unchanged.

> Why not TiDB, PlanetScale or SQLite? TiDB doesn't support stored procedures, PlanetScale has no free tier,
> and SQLite has no stored procedures at all.

Total time: about 30 minutes. You need a GitHub account with this project pushed to it (see
[SUBMISSION_GUIDE.md](SUBMISSION_GUIDE.md), step 2).

---

## Part 1: create the MySQL database on Aiven

1. Go to <https://console.aiven.io/signup> and sign up (GitHub sign-in works).
2. Click **Create service** → **MySQL**.
3. Choose **Free plan**, any cloud/region (pick one close to Render's *Oregon* or *Ohio*, e.g. AWS `us-west`), and name it `xfactor-mysql`.
4. Click **Create free service** and wait until the status dot turns green (*Running*, about 2–5 minutes).
5. On the service's **Overview** page, note the connection info:

   ```
   Host:     xfactor-mysql-<you>.aivencloud.com
   Port:     12345           (a 5-digit port, not 3306)
   User:     avnadmin
   Password: (click the eye icon to reveal)
   ```

6. Under **CA certificate**, click **Download** and save it as `aiven-ca.pem` in the project folder.
   It's already git-ignored; don't commit it.

## Part 2: load the data into Aiven from your Mac

1. Make a second env file for the cloud database (keep your local `.env` as it is):

   ```bash
   cp .env .env.aiven
   ```

   Edit `.env.aiven`:

   ```ini
   DB_HOST=xfactor-mysql-<you>.aivencloud.com
   DB_PORT=12345
   DB_NAME=xfactor
   DB_USER=avnadmin
   DB_PASSWORD=<aiven password>
   DB_SSL_CA=./aiven-ca.pem
   DB_READONLY_USER=xfactor_ro
   DB_READONLY_PASSWORD=<make up a strong password>
   ```

2. Load the schema and data:

   ```bash
   source .venv/bin/activate
   set -a; source .env.aiven; set +a
   python -m xfactor.loader
   ```

   You should see the table counts (`TOTAL: 5075`).

3. Create the read-only user for the Ask page. Run this from the same shell (it reuses the variables you just loaded):

   ```bash
   python - <<'EOF'
   import os
   from sqlalchemy import text
   from xfactor.db import get_engine
   pw = os.environ["DB_READONLY_PASSWORD"]
   with get_engine().begin() as c:
       c.execute(text(f"CREATE USER IF NOT EXISTS 'xfactor_ro'@'%' IDENTIFIED BY '{pw}'"))
       c.execute(text("GRANT SELECT, SHOW VIEW ON xfactor.* TO 'xfactor_ro'@'%'"))
   print("read-only user ready")
   EOF
   ```

4. Open a **new terminal** afterwards (or run `set -a; source .env; set +a`) so later commands use your local database again.

## Part 3: deploy the web app on Render

1. Go to <https://dashboard.render.com> and sign up with GitHub.
2. Click **New +** → **Blueprint**, select your `XFactor-Database-System` repository, and click **Connect**.
   Render reads [render.yaml](../render.yaml) and proposes a web service named `xfactor-uk-db`.
3. Render asks for the values marked `sync: false`. Enter:

   | Key | Value |
   |---|---|
   | `DB_HOST` | Aiven host |
   | `DB_PORT` | Aiven port |
   | `DB_USER` | `avnadmin` |
   | `DB_PASSWORD` | Aiven password |
   | `DB_READONLY_USER` | `xfactor_ro` |
   | `DB_READONLY_PASSWORD` | the read-only password from Part 2 |
   | `ANTHROPIC_API_KEY` | your key (see SUBMISSION_GUIDE step 4) |
   | `EDIT_PASSWORD` | a password **you** choose. The public can browse, but only someone with this can edit |

4. Click **Apply**. Then open the new service → **Environment** → **Secret Files** → **Add Secret File**:
   - Filename: `ca.pem`
   - Contents: paste the full text of `aiven-ca.pem`, including the `-----BEGIN CERTIFICATE-----` lines.

   Click **Save Changes**. Render redeploys automatically.
5. Watch **Logs** until you see `Booting worker`. Your URL appears at the top of the page, like
   `https://xfactor-uk-db.onrender.com`.

### Check it works

- The home page shows 16 tables and `5,075` rows.
- **Procedures → sp_series_leaderboard** returns a table.
- **Ask ✨** answers "Which mentor has won the most series?"
- **Log in** with `EDIT_PASSWORD`, then create and delete a row in `hometown`.

> **Free-tier behaviour:** Render puts free services to sleep after 15 minutes without traffic. The first
> visit afterwards takes about 30–60 seconds. **Open the site a couple of minutes before you present.**
> Aiven's free MySQL powers off after a long idle period. If the site shows a database error, open the
> Aiven console and click **Power on**.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `Can't connect to MySQL server` during the load | Check host and port in `.env.aiven`, and that the Aiven service is *Running* |
| `SSL: CERTIFICATE_VERIFY_FAILED` | `DB_SSL_CA` must point at the downloaded `aiven-ca.pem` (on Render: the secret file `/etc/secrets/ca.pem`) |
| `Access denied ... to database 'xfactor_test'` when running `pytest` against Aiven | Expected: run tests against your local database only |
| Ask page says "Set ANTHROPIC_API_KEY" | Add the key under Render → Environment, then redeploy |
| Edits redirect to the login page | Expected when `EDIT_PASSWORD` is set: log in first |
