# Daily Instagram cucumber post

This project publishes `images/cucumber.jpg` to Instagram once per day using
the Instagram Graph API. It uses only Python's standard library.

## Requirements

- An Instagram **Professional** account (Business or Creator) linked to a
  Facebook Page.
- A long-lived access token with `instagram_basic`, `pages_show_list`,
  `pages_read_engagement`, and `instagram_content_publish` permissions.
- The numeric Instagram account ID.
- A public HTTPS URL for `images/cucumber.jpg`. Instagram fetches the image
  from a URL; it cannot publish a file that exists only on this computer.

## Configure

Copy the example and fill in the three required values:

```bash
cp .env.example .env
```

`INSTAGRAM_IMAGE_URL` should point to an unchanged, publicly downloadable copy
of `images/cucumber.jpg`. Do not commit `.env`; it contains a secret token.

Test one post manually:

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
