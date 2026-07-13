# Daily Instagram cucumber post

This project publishes `images/cucumber.jpg` to Instagram once per day using
the Instagram Graph API. It uses only Python's standard library.

The default `GRAPH_API_HOST` is `graph.instagram.com`, for access tokens created
through **Instagram > API setup with Instagram business login**. Tokens created
through Facebook Login use a different host and permission flow.

## Set up Poetry

Please follow the official [installation guide](https://python-poetry.org/docs/#installation) to install Poetry, which will be used to manage dependencies and environments.

```bash
# Install dependencies
poetry install
```

```bash
# Activate Python Virtual Environment for Mac/Linux
eval "$(poetry env activate)"

# Activate Python Virtual Environment for Windows
.venv\Scripts\Activate.ps1
```

## Set up environment variables

```bash
# Create .env file (by copying from .env.example)
cp .env.example .env
```

## Test one post manually

```bash
./run_daily.sh
```

On success, the script records the current local date in
`.last_successful_post`. Further runs that day are safely skipped. Delete that
file only if you intentionally want to post again on the same day.

## Install the cron job

The default schedule is every day at 9:00 AM in the computer's local timezone:

```bash
./install_cron.sh
```

To choose another cron schedule, for example 6:30 PM:

```bash
CRON_SCHEDULE="30 18 * * *" ./install_cron.sh
```

The installer replaces any earlier entry created by this project, preserves
other crontab entries, and writes output to `instagram-cron.log`. The computer
must be awake and connected at the scheduled time.

Run the tests with:

```bash
python3 -m unittest discover -s tests
```
