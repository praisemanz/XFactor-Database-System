# Submission guide: steps to do yourself

Everything that could be done from the terminal is done: scraping, schema, ORM, data, views, procedures,
CLI, GUI, the LLM page, tests, the ERD file and the docs. These are the steps that need your accounts,
your browser or you in person, in the order to do them.

| # | Step | Needed for | Time |
|---|---|---|---|
| 1 | Reserve the topic | Step 2 of the PDF (required) | 2 min |
| 2 | Push to GitHub | +3% and Render deploy | 10 min |
| 3 | Check the ERD in draw.io and export a PNG | Step 3 (required) and slides | 10 min |
| 4 | Get an Anthropic API key | EC 7b | 5 min |
| 5 | Deploy online | EC 7c | 30 min |
| 6 | Capture evidence of 2,000+ rows | EC 7d | 5 min |
| 7 | Finish the slides and rehearse | Steps 8b and 9 (required) | 1–2 h |
| 8 | Submit | Step 8 | 5 min |

---

## 1. Reserve the topic

Open the sign-up link in the PDF (step 2b, "Sign up **here**") and register:

- **Group:** your name (group of 1)
- **Wiki:** *The X Factor (UK)*: `https://en.wikipedia.org/wiki/The_X_Factor_(British_TV_series)`

Do this first: no two groups may use the same wiki.

## 2. Push the project to GitHub (+3%)

1. Go to <https://github.com/new>. Name it `XFactor-Database-System`, choose **Public** (the grader must
   be able to open it), and **don't** add a README or .gitignore (the project has both).
2. In the project folder:

   ```bash
   cd ~/XFactor-Database-System
   git status                         # .env, .venv and *.pem must NOT be listed
   git add .
   git commit -m "feat: add X Factor UK database, ORM, CLI, web GUI and NL query"
   git branch -M main
   git remote add origin https://github.com/<your-username>/XFactor-Database-System.git
   git push -u origin main
   ```

3. Refresh the GitHub page. The README renders with the requirement checklist, and
   `docs/erd.md` shows the diagram (GitHub renders Mermaid).

> If `git status` lists `.env`, **stop**. It holds your database passwords. Check that `.gitignore`
> is in the folder before you `git add`.

## 3. ERD in draw.io

The diagram is generated from the code (`python -m xfactor.erd`), so it matches the database exactly.

1. Go to <https://app.diagrams.net> → **Open Existing Diagram** → choose `docs/erd.drawio`
   (or drag the file onto the page).
2. You'll see 16 tables in a 4×4 grid with crow's-foot lines for every foreign key:
   - **Blue row:** people and series (`person`, `series_judge`, `series`, `series_presenter`)
   - **Green row:** categories and mentoring (`mentorship_assistant`, `mentorship`, `category`, `episode`)
   - **Yellow row:** contestants (`hometown`, `series_act`, `act`, `music_release`)
   - **Red row:** music and performances (`artist`, `song`, `performance`, `live_show`)
3. Some connector lines may cross. Drag any table to tidy it; the lines follow.
4. **File → Export as → PNG** (zoom 200%, border 20) → save as `docs/erd.png` for the slides.
5. **File → Save** to keep your layout changes in `erd.drawio`.

**Normalisation talking points** (for the slides):
- **1NF:** no repeating groups. A judge panel is rows in `series_judge`, not a "judges" text column. Songs in a multi-song week are separate `performance` rows.
- **2NF:** junction tables (`series_judge`, `series_presenter`, `mentorship_assistant`) hold only facts about the whole composite key, such as `is_guest`.
- **3NF:** names live in exactly one place. `act`, `person`, `artist`, `hometown` and `category` are looked up by id, so "Simon Cowell" is stored once even though he mentored in 12 series.
- `series_act` resolves the many-to-many between acts and series and carries per-run facts (age, hometown, final position).

## 4. Anthropic API key (for the Ask page)

1. Go to <https://console.anthropic.com> and sign in.
2. **Settings → Billing**: add a small credit (US$5 is plenty: each question costs about one cent).
3. **Settings → API keys → Create key**. Name it `xfactor`, then copy the key (it starts with `sk-ant-`).
4. Paste it into `.env`: `ANTHROPIC_API_KEY=sk-ant-...`. Never commit it.
5. Restart the GUI (`python -m xfactor.web`) and open <http://127.0.0.1:5050/ask>. Try the example chips.

## 5. Deploy online (EC 7c)

Follow [DEPLOYMENT.md](DEPLOYMENT.md) (Aiven MySQL + Render). Write the URL down for submission.

## 6. Evidence for 2,000+ rows (EC 7d)

Take either or both screenshots:
- The GUI home page: it shows **"5,075 rows across 16 tables"** and a tile per table.
- MySQL Workbench, running:

  ```sql
  SELECT 'performance' t, COUNT(*) n FROM performance UNION ALL
  SELECT 'song', COUNT(*) FROM song UNION ALL
  SELECT 'music_release', COUNT(*) FROM music_release UNION ALL
  SELECT 'episode', COUNT(*) FROM episode UNION ALL
  SELECT 'TOTAL (all 16 tables)', (SELECT SUM(table_rows) FROM information_schema.tables WHERE table_schema='xfactor');
  ```

  (`table_rows` in `information_schema` is an estimate; the home page count is exact.)

Mention the source: the data comes from Wikipedia's series and discography tables via the MediaWiki API,
parsed by `xfactor/scraper/`.

## 7. Slides and rehearsal (4–7 minutes)

A draft deck has been prepared (link in the chat). Add your ERD PNG and screenshots. Suggested **6-minute demo
script**, which covers every required item from step 9c:

| Time | Show | Say |
|---|---|---|
| 0:00 | Title slide | Topic, data source, 16 tables / 5,075 rows |
| 0:30 | ERD slide | Main entities; how `series_act` and `mentorship` normalise the data |
| 1:15 | Terminal: `python -m xfactor.cli`, option **5** | **CONSTRAINT**: CHECK rejects series 150; UNIQUE rejects a second "Little Mix" |
| 1:45 | Option **6** | **INDEX**: `SHOW INDEX`, then `EXPLAIN` shows `key = ix_song_title` |
| 2:15 | Option **7**, mentor `Tulisa` | **JOIN**: 8-table ORM join of songs by mentor |
| 2:45 | Option **8**, `v_series_summary` | **VIEW**: every winner and runner-up |
| 3:10 | Option **9** → `1`, series `8` | **STORED PROCEDURE**: leaderboard |
| 3:35 | Option **10** | **UPDATE**: change a show's theme, before → after |
| 4:00 | Browser GUI | EC 7a: edit a `hometown` row, then delete it |
| 4:40 | Ask page | EC 7b: "Which mentor has won the most series?", then show the generated SQL |
| 5:20 | Deployed URL | EC 7c |
| 5:40 | Problems / learned slide | Close |

**Problems you hit** (true, and worth saying):
- Wikipedia tables use `rowspan`/`colspan`. A copied song cell looked like an artist until the parser checked for it.
- The same person appears under different names ("Cheryl Cole", "Cheryl Fernandez-Versini", "Cole"), and Little Mix started as "Rhythmix". Normalisation needed an alias map.
- `RELEASE` is a reserved word in MySQL, so the table is `music_release`.
- PyMySQL treats `%` in `LIKE '%…%'` as a format placeholder, so procedures are sent through a raw cursor.
- A read-only session setting leaked into pooled connections. Fixed by scoping it to one transaction, and a test catches it.
- LLM-generated SQL is untrusted input. It gets a guard, a SELECT-only user, a read-only transaction and a time limit.

Rehearse with a timer. If it runs over 7 minutes, cut the GUI segment to one edit.

## 8. Submit

- **Code:** the GitHub URL (+3%), or a zip if you skip GitHub. To make a zip without secrets:
  `git archive -o xfactor.zip HEAD`
- **Slides:** export the deck to PDF or PPTX.
- **Extra credit:** the deployed URL (7c) and the screenshot from step 6 (7d).
- **Contributions:** as a group of one, add a slide or line describing your role. Check your course's
  policy on AI tools. If it asks for disclosure, state that you used an AI coding assistant and describe what
  you reviewed, changed and tested yourself. Make sure you can explain every part of the code in the Q&A.
