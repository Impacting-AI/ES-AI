# Run PM AI ES on your laptop

## Mac setup

1. Install Docker Desktop for your Mac. Open it and wait until Docker is running. Also have an authenticator app available for the six-digit sign-in code. Internet is needed for the first build and for external services.
2. Download the source ZIP and double-click it in Finder. Find the folder containing **Start.command**, **compose.yaml** and **Dockerfile**. Keep this folder in one permanent location.
3. Open Terminal. Type `cd ` with a space, drag that folder into Terminal and press Return. Then run:

   ```bash
   bash Start.command
   ```

4. The launcher creates two private installation keys in `.env`, builds the web app, starts PostgreSQL and creates its tables. On first installation, enter your admin username or email and a password of at least 14 characters. Terminal hides the password while you type.
5. The launcher displays a setup key. In your authenticator, add an account using a setup key and choose **time based**. Store the key privately. Wait for the launcher to say the application is ready.
6. Open **http://localhost:8080**. Enter the same username and password, plus the current six-digit code. Docker runs the frontend, backend and report worker together.
7. Open **Projects → Create project**. Enter a project and client name. Open it, upload a small text scope and approve it. In **AI PM chat**, turn **Response OFF** and save a note. Refresh, reopen the project and search the Documents screen for a word in the note.
8. Open **Agents → AI model** to enable genuine AI responses. Follow CONFIGURATION-GUIDE.md for model, Jira, Slack and email settings. First test against an internal project and a recipient you control.

## Stop, restart and inspect

Run these commands in the same project folder.

| Goal | Command |
|---|---|
| Stop the app and keep your data | `docker compose stop` |
| Start again | `docker compose start` |
| Apply updated code or migrations | `bash Start.command` |
| Check services | `docker compose ps` |
| Read recent errors | `docker compose logs --tail 50 app worker db` |
| Test authentication, project isolation and database restart in a separate disposable database | `bash tests/check-stack.sh` |
| Test configured accounts on a disposable installation | `docker compose exec app python -m tests.live_acceptance` |
| Recover a login from the trusted laptop terminal | `docker compose run --rm app python -m server.admin` and enter the original username to reset its password and authenticator |
| Add an employee login | `docker compose run --rm app python -m server.admin --role Employee` |

The PostgreSQL data lives in a Docker volume. Keep the installation folder, Compose project name and original .env together. Removing volumes deletes data. The backend and frontend share port 8080. If it is occupied, close the other application using it and rerun the launcher.

## Windows and Linux

On Linux with Docker Engine and the Compose plugin, run the same Bash commands. On Windows use Docker Desktop with WSL integration, extract the project into your WSL home folder, open its Ubuntu terminal and run the Bash steps. If Windows opens the preview rather than the installed app, enter http://localhost:8080 in your browser. These platform paths await hands-on verification.

## Manual development setup

Use Python 3.12, Node 22 with npm and a running PostgreSQL 16 server. Create a database and a login that owns it. From the project folder:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
npm install
npm run build
export PUBLIC_ORIGIN=http://localhost:8080
export DATABASE_URL='postgresql://YOUR_USER:YOUR_PASSWORD@localhost/YOUR_DATABASE'
export ENCRYPTION_KEY="$(python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())')"
python -m server.migrate
python -m server.admin
uvicorn server.app:app --host 127.0.0.1 --port 8080
```

Save the generated encryption key privately and reuse it for every subsequent launch. In another terminal activate the same virtual environment, set the **same** three environment variables, then run `python -m server.worker`. Open http://localhost:8080. Stop each process with Ctrl+C. FastAPI serves the compiled React app. Rebuild with `npm run build` after editing frontend code.

## Back up and recover

In the project directory run `docker compose exec -T db pg_dump -U pm -Fc pm > pm-backup.dump`. Store that file and a protected copy of the matching .env separately from the laptop. Both the dump and key are sensitive. For a recovery drill use a separate installation with matching encryption key and an empty database. Start only its database, then run `docker compose exec -T db pg_restore -U pm -d pm --exit-on-error < pm-backup.dump`. Run the migration, start app and worker and verify a login and a test document. Restore has not been executed in this audit.
