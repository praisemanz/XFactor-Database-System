# MySQL setup

There are two ways to run the database locally. Pick one.

## Option A: the private MySQL 8.0.35 already set up on this Mac (port 3310)

This is what `.env` currently points at. It lives outside the repo:

| What | Where |
|---|---|
| Server binaries | `~/mysql-8.0.35/` |
| Data + config | `~/mysql-data/` (`my.cnf`, `data/`, `mysqld.err`) |
| Root password | `~/mysql-data/root-password.txt` (readable only by you) |
| App users | `xfactor_app` (full rights on `xfactor`, `xfactor_test`) and `xfactor_ro` (SELECT only), passwords in `.env` |

It does **not** start automatically after a reboot. To start it:

```bash
~/mysql-8.0.35/bin/mysqld --defaults-file=$HOME/mysql-data/my.cnf &
```

To stop it:

```bash
~/mysql-8.0.35/bin/mysqladmin -uroot -p"$(cat ~/mysql-data/root-password.txt)" -h127.0.0.1 -P3310 shutdown
```

### Viewing it in MySQL Workbench

1. Open **MySQL Workbench** and click the **⊕** next to *MySQL Connections*.
2. Fill in:
   - Connection Name: `X Factor (3310)`
   - Hostname: `127.0.0.1`, Port: `3310`
   - Username: `xfactor_app`
   - Password: click **Store in Keychain…** and paste `DB_PASSWORD` from `.env`
   - Default Schema: `xfactor`
3. Click **Test Connection**, then **OK**, and open the connection.
4. In the *Navigator → Schemas* panel, expand `xfactor` to see **Tables**, **Views** and **Stored Procedures**.

To show the ERD inside Workbench as well: **Database → Reverse Engineer…**, choose the connection, pick
the `xfactor` schema, and finish. Workbench draws a diagram from the foreign keys.

## Option B: your existing MySQL 9.7 server (port 3306)

You already run MySQL 9.7 from `/usr/local/mysql` (the one Workbench probably connects to by default).
To use it instead:

1. In Workbench, connect as **root** to your 3306 server and run this in a SQL tab, choosing your own password:

   ```sql
   CREATE USER 'xfactor_app'@'localhost' IDENTIFIED BY 'choose-a-password';
   CREATE USER 'xfactor_app'@'127.0.0.1' IDENTIFIED BY 'choose-a-password';
   GRANT ALL PRIVILEGES ON xfactor.*      TO 'xfactor_app'@'localhost', 'xfactor_app'@'127.0.0.1';
   GRANT ALL PRIVILEGES ON xfactor_test.* TO 'xfactor_app'@'localhost', 'xfactor_app'@'127.0.0.1';
   CREATE USER 'xfactor_ro'@'127.0.0.1' IDENTIFIED BY 'choose-another-password';
   GRANT SELECT, SHOW VIEW ON xfactor.* TO 'xfactor_ro'@'127.0.0.1';
   ```

2. Edit `.env`: set `DB_PORT=3306` and the two passwords you chose.
3. Load everything:

   ```bash
   source .venv/bin/activate
   python -m xfactor.loader
   pytest            # optional: confirms everything works on this server
   ```

4. You can then stop the private 3310 server (command above) and delete `~/mysql-8.0.35` and `~/mysql-data`.

> **Note:** XAMPP's MariaDB also runs on this Mac on port **3307**. Don't point the project at it:
> MariaDB handles CHECK constraints and some MySQL 8 features differently.
