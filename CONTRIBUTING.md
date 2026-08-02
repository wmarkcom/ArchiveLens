# Contributing to ArchiveLens

Thanks for taking an interest in ArchiveLens. The project is an early self-hosted MVP, so small, focused contributions are the easiest to review.

## Development Setup

1. Create the Python environment:

```bash
conda env create -f environment.yml
conda activate archivelens
```

2. Install browser dependencies used by the platform probes:

```bash
python -m playwright install chromium
```

3. Start the backend:

```bash
uvicorn app.main:app --app-dir backend --reload --host 0.0.0.0 --port 8000
```

4. Start the frontend:

```bash
cd frontend
npm install
npm run dev
```

## Pull Request Checklist

- Keep platform sessions, cookies, webhook URLs, database credentials, and real `.env` files out of commits.
- Add or update tests when changing parsers, adapters, worker behavior, or API contracts.
- Run backend tests before submitting:

```bash
pytest
```

- Run the frontend type check and build before submitting:

```bash
cd frontend
npm run build
```

## Project Boundaries

ArchiveLens is intended for archiving content from accounts that the user is authorized to access. Contributions should not add CAPTCHA bypasses, proxy rotation, shared cookie pools, scraping evasion, or other behavior intended to bypass platform protections.
