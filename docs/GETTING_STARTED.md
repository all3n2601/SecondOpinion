# Getting started

Step-by-step instructions for macOS, Linux and Windows. For the short version, see the [README](../README.md#quick-start).

These steps work on macOS, Linux and Windows. Where the commands differ, both are given: **macOS /
Linux** in a terminal, **Windows** in PowerShell (Windows Terminal or the VS Code terminal). They take
about 10 minutes the first time, most of it downloading.

## Step 1. Check you have the tools

Run each command and check the version it prints.

macOS / Linux:

```bash
node --version      # needs v22 or newer
python3 --version   # needs 3.11, 3.12, 3.13 or 3.14
git --version       # any version
```

Windows (PowerShell):

```powershell
node --version      # needs v22 or newer
py --list           # the Python launcher lists installed versions; needs 3.11, 3.12, 3.13 or 3.14
git --version       # any version
```

If Node is missing or older than 22, install it from <https://nodejs.org> (or `nvm install 22`). If
Python is missing or too old, install it from <https://www.python.org/downloads/>. If git is missing,
install it from <https://git-scm.com/downloads>.

On Windows you can install all three with winget instead, then open a **new** PowerShell window so
they are on the `PATH`:

```powershell
winget install OpenJS.NodeJS.LTS Python.Python.3.13 Git.Git
```

If `py` is not found, use `python` instead in the Windows commands below (check `python --version`
first; the Microsoft Store placeholder prints nothing useful, so install from python.org or winget).

## Step 2. Get the code

```bash
git clone https://github.com/all3n2601/SecondOpinion.git
cd SecondOpinion
```

Run every remaining command from inside this `SecondOpinion` folder unless the step says otherwise.

## Step 3. Install the Python part

macOS / Linux:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Windows (PowerShell):

```powershell
py -3.13 -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

This creates a `.venv` folder inside `SecondOpinion`. The app expects it there, so don't put it anywhere
else (the npm scripts find `.venv/bin/python` or `.venv\Scripts\python.exe` on their own). If
`python3` is older than 3.11, use the full name of a newer one instead, for example
`python3.13 -m venv .venv`; on Windows, change `-3.13` to any version `py --list` shows from 3.11 to 3.14.

## Step 4. Install the web part

```bash
npm ci
```

On Windows, if PowerShell says `npm.ps1 cannot be loaded because running scripts is disabled`, run
`Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once (or type `npm.cmd` instead of `npm`). Stop any
running `npm run dev` first: Windows will not let `npm ci` replace files a running server has open.

## Step 5. Download the data

The data is not stored in this repository. Get it from the organizers' repository, which goes in the
folder **next to** `SecondOpinion`, not inside it.

macOS / Linux:

```bash
git clone https://github.com/disleveK/oncosys-hackathon-challenge.git ../oncosys-hackathon-challenge
.venv/bin/python ../oncosys-hackathon-challenge/data/tcga-brca/fetch.py
```

Windows (PowerShell):

```powershell
git clone https://github.com/disleveK/oncosys-hackathon-challenge.git ..\oncosys-hackathon-challenge
.venv\Scripts\python.exe ..\oncosys-hackathon-challenge\data\tcga-brca\fetch.py
```

This downloads the TCGA-BRCA release (about 70 MB) and checks every file. If it prints `CHANGED` for a
file, stop and tell the organizers.

## Step 6. Note the full path to the data folder

The app asks for this path. Print it.

macOS / Linux:

```bash
(cd ../oncosys-hackathon-challenge/data/tcga-brca/raw && pwd)
```

Windows (PowerShell):

```powershell
(Resolve-Path ..\oncosys-hackathon-challenge\data\tcga-brca\raw).Path
```

Copy the line it prints, for example `/Users/you/oncosys-hackathon-challenge/data/tcga-brca/raw` or
`C:\Users\you\oncosys-hackathon-challenge\data\tcga-brca\raw`.

To skip pasting it every time, save it once. This is optional:

```bash
cp apps/web/.env.example apps/web/.env.local                 # macOS / Linux
Copy-Item apps\web\.env.example apps\web\.env.local          # Windows (PowerShell)
```

Then open `apps/web/.env.local` and paste the path after `NEXT_PUBLIC_DEFAULT_RELEASE_DIR=`. A Windows
path with backslashes works as it is; don't add quotes.

## Step 7. Start the app

```bash
npm run dev
```

This starts the website and the API together. Leave this terminal open; the app stops when you close
it. When you see `Ready` from the website, go to the next step.

## Step 8. Open it in your browser

Go to **<http://localhost:3000>**. Use `localhost`, not `127.0.0.1`; on `127.0.0.1` the page will not
load properly.

Click **Start an audit**. The Start page should say **API connected**. If it says the API is unavailable,
check the terminal from step 7 for an error.

## Step 9. Run the practice audit

1. You can leave the data folder box empty: the practice run fills it in with release A (the copy
   from step 6, or a temporary download of about 70 MB if there is none).
2. Click **Run the practice audit**. It reads the organizers' practice report and checks its three
   claims.
3. Click **Open the audit board** to see each claim's verdict. Click **Open evidence** on a claim to see
   how it was checked.
4. To finish: on **Review**, accept or override each verdict. Then on **Decision**, choose a decision,
   give a reason and click **Export** to download `audit.json` and the Decision Record.

To audit your own report instead, upload it (Markdown, text or PDF) or paste its text on the Start
page.

## Step 10. Stop the app

Go back to the terminal from step 7 and press **Ctrl+C**. On Windows, if it asks
`Terminate batch job (Y/N)?`, type `Y`.

## Running it again later

You only need steps 7 to 9:

```bash
cd SecondOpinion
npm run dev
```

## Without the browser (optional)

To check a report (`.md`, `.txt` or `.pdf`) from the terminal instead:

```bash
.venv/bin/second-opinion --release ../oncosys-hackathon-challenge/data/tcga-brca/raw \
  --report path/to/report.md --out audit.json
```

Windows (PowerShell):

```powershell
.venv\Scripts\second-opinion.exe --release ..\oncosys-hackathon-challenge\data\tcga-brca\raw `
  --report path\to\report.pdf --out audit.json
```

It prints one line per claim and writes `audit.json`.

If something goes wrong, see [Troubleshooting](DEVELOPMENT.md#troubleshooting).
