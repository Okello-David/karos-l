# CloudWatch Monitoring

Status: **live since 2026-08-19.** Basic observability for the live pilot — detect application, infra,
container, and backup failures before a user does. This doc is the reference for what's monitored, why,
and how to respond.

Nothing here existed before today — confirmed directly (`aws logs describe-log-groups`, `describe-alarms`,
`sns list-topics`, `list-dashboards` all returned empty before this work started).

## 1. Architecture

```
karosl.log (Django, WARNING+)        ──┐
/home/ec2-user/logs/karosl-backup.log ─┼──► CloudWatch Agent (file tailing) ──► CloudWatch Logs
  (backup script output, tee'd)        ─┘        + disk/mem metrics

nginx (frontend container stdout)  ────────► Docker awslogs driver ─────────► CloudWatch Logs

EC2 StatusCheckFailed / CPUUtilization (built-in) ──┐
disk_used_percent (CloudWatch Agent metric) ─────────┼──► CloudWatch Alarms ──► SNS ──► email
BackupFailures (metric filter on backup log group) ──┘
```

Two design decisions worth knowing, verified empirically rather than assumed (see `docs/PROJECT_STATE.md`
for the full account):

- **Log shipping uses file tailing everywhere, not systemd-journal collection.** The CloudWatch Agent
  version AL2023's `dnf` repo actually installs (1.300067.1) predates native journald support (added in
  1.300070.0, a few weeks newer) — confirmed by installing it and grepping its own config schema for any
  mention of journald (none). So `karosl-backup.service`'s `ExecStart` is wrapped in `tee -a
  ~/logs/karosl-backup.log` (in addition to, not instead of, its existing journal output —
  `journalctl -u karosl-backup.service` keeps working exactly as before), giving the agent a stable file to
  tail. `set -o pipefail` in that wrapper is load-bearing, not decorative: without it, a POSIX pipeline's
  exit status is `tee`'s (always 0), and a failed backup would silently report success to systemd.
- **Nginx logs ship via Docker's own `awslogs` logging driver, not the CloudWatch Agent.** The official
  nginx image symlinks its access/error logs to `/dev/stdout`/`/dev/stderr`, captured by Docker's default
  logging driver as JSON-wrapped lines keyed by a container ID that changes on every recreate — file-tailing
  that path reliably would need tracking a moving target. Docker's built-in `awslogs` driver handles the
  container-identity problem internally and ships stdout/stderr directly; no separate agent needed for this
  one source.

**No duplication**: Django's `karosl.log` (already WARNING+-filtered) is the only Django source shipped —
its container's raw stdout is deliberately *not* also shipped, since that would just duplicate the same
events into a second stream for no benefit.

## 2. Log groups

| Log group | Source | Retention |
|---|---|---|
| `/karosl/staging/django` | `karosl.log` (Django, WARNING+ — unhandled exceptions, 4xx/5xx including auth failures, custom `karosl` logger) | 14 days |
| `/karosl/staging/nginx` | frontend container stdout/stderr (access + error logs) | 14 days |
| `/karosl/staging/backup` | `backup-to-s3.sh`/`restore-from-s3.sh` `[EVENT]` markers and full run output | 14 days |

**Why 14 days, not longer:** this is a small live pilot, not a compliance-driven retention need. 14 days
covers "did this happen again this week" and "what changed since last week" — the realistic troubleshooting
window at this scale — while keeping storage cost negligible. Log ingestion here is a handful of KB/day
across all three groups; even at zero retention discipline the monthly cost would round to nothing, so 14
days is chosen for signal-to-noise (a long-lived log group accumulates enough routine 401-scanning-bot noise
to make Logs Insights queries slower to reason about, not because 14 days costs meaningfully less than 90).
No log group here is expected to need forever-retention — extend later if a real need appears, don't
pre-provision for a hypothetical one.

## 3. IAM

New inline policy `karosl-cloudwatch-logs-metrics` on the existing `karosl-staging-backup-role` (reused, not
a second role — it's already the instance's one role):

```json
{
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "WriteKarosLLogs",
            "Effect": "Allow",
            "Action": ["logs:CreateLogGroup", "logs:CreateLogStream", "logs:PutLogEvents", "logs:DescribeLogStreams"],
            "Resource": [
                "arn:aws:logs:eu-north-1:908877263055:log-group:/karosl/staging/*",
                "arn:aws:logs:eu-north-1:908877263055:log-group:/karosl/staging/*:log-stream:*"
            ]
        },
        {
            "Sid": "PutCloudWatchMetrics",
            "Effect": "Allow",
            "Action": "cloudwatch:PutMetricData",
            "Resource": "*"
        }
    ]
}
```

`cloudwatch:PutMetricData` is the one action here that genuinely cannot be resource-scoped — AWS does not
support ARN-level restriction on it (a documented limitation of the action, not an oversight in this
policy). Everything else is scoped to exactly the `/karosl/staging/*` log group prefix. Not granted, and
verified absent: `s3:*`-style wildcards, `logs:DeleteLogGroup`, any `cloudwatch:*` beyond the one metric-write
action, access to any log group or namespace outside this prefix.

Docker's `awslogs` driver and the CloudWatch Agent both use the instance's IAM role automatically via the
standard credential chain (EC2 instance metadata) — no keys anywhere, confirmed by the absence of
`~/.aws/credentials` on the box (same posture as the S3 backup role from earlier today).

## 4. Application logging (Task 4) — already covered, not newly added

Reviewed `backend/config/settings.py`'s `LOGGING` dict and confirmed empirically against the live instance,
rather than assumed from the config alone:

- **Unhandled exceptions**: Django's `django.request` logger already captures 5xx responses at ERROR
  (with traceback) through both the `console` and `file` handlers.
- **Authentication failures**: confirmed live — `karosl.log` already contains lines like
  `WARNING 2026-08-19 ... Unauthorized: /api/reports/occupancy/` for every 401. Django's request-logging
  middleware logs every non-2xx response, 401s included, at WARNING+ by default; no custom signal handler
  was needed.
- **Important warnings**: root logger level is INFO, `file` handler threshold is WARNING — routine INFO
  noise stays out of the persisted file (and therefore out of CloudWatch) while anything WARNING+ is kept.

**Not logged, verified by inspection of the logging call sites**: passwords, tokens, database credentials,
AWS credentials. Django/DRF's default request logging logs the path and status phrase, not headers or
request bodies, so credentials never enter a log line in the first place — there's no redaction step because
there's nothing to redact.

## 5. Nginx logging (Task 5) — default format kept, not changed

`frontend/nginx.conf` and the HTTPS templates carry no explicit `access_log`/`error_log` directives, so
nginx uses its compiled-in default (the standard `combined` format, which includes `$status`). That's
sufficient to identify repeated 4xx/5xx once shipped (Task 3) — a CloudWatch Logs Insights query filtering
`/karosl/staging/nginx` by status code answers "how many 500s in the last hour" directly. A custom
`log_format` adding `$upstream_status`/`$upstream_response_time` was considered and deliberately not done:
it would need a `log_format` directive in the *http*-level config this repo doesn't currently own (these
templates are server-block-only, included into the base nginx image's http block), for a live pilot at a
scale where `$status` alone already answers the question asked. Revisit if request-level upstream timing
ever becomes a real debugging need.

## 6. Backup monitoring (Task 6)

Two CloudWatch Logs metric filters on `/karosl/staging/backup`, both in namespace `KarosL/Staging`:

| Filter | Pattern | Metric |
|---|---|---|
| `karosl-backup-failures` | `?"BACKUP_FAILED" ?"UPLOAD_FAILED"` | `BackupFailures` |
| `karosl-backup-successes` | `"BACKUP_SUCCEEDED"` | `BackupSuccesses` |

These match the `[EVENT]` markers `scripts/backup-to-s3.sh` already emits (added earlier today —
`docs/S3_BACKUP_ARCHITECTURE.md` §11 described exactly this as deferred future work; this is that work).
**Verified for real, not just configured**: a deliberate `KAROSL_BACKUP_BUCKET` override pointed at a
nonexistent bucket, run through `systemctl start karosl-backup.service` (exercising the real tee/systemd
path, not a bypass), produced `[EVENT] UPLOAD_FAILED stage=upload`, `systemctl is-failed` correctly reported
`failed`, the log line reached CloudWatch, `aws logs test-metric-filter` confirmed the pattern matches it,
and `BackupFailures` showed `Sum=1` within about a minute.

## 7. Alarms

Four, each documented here with what it detects, its threshold, and the expected response — matching "not
dozens of alarms":

| Alarm | Metric | Threshold | Notification | Expected response |
|---|---|---|---|---|
| `karosl-staging-status-check-failed` | `AWS/EC2 StatusCheckFailed` (built-in, no agent needed) | ≥1 for 1×5min | SNS on ALARM and OK | Check the instance in the EC2 console; a *system*-status failure may need stop/start (not reboot) to move to new host hardware. |
| `karosl-staging-high-cpu` | `AWS/EC2 CPUUtilization` | >80% sustained 15min (3×5min) | SNS on ALARM and OK | `docker stats` / `docker compose logs` for a runaway process; a brief spike isn't alarming, sustained load might be a stuck request loop or abusive traffic. |
| `karosl-staging-low-disk` | `KarosL/Staging disk_used_percent` (CloudWatch Agent, dimensions `path=/,device=nvme0n1p1,fstype=xfs,host=<internal-hostname>` — the agent auto-tags these; a dimensionless query finds nothing, a real gotcha hit and fixed during setup) | >85% for 2×5min | SNS on ALARM and OK | `docker system df` and prune old images; local backup dumps already auto-prune to 3 (`KEEP_LOCAL`). |
| `karosl-staging-backup-failed` | `KarosL/Staging BackupFailures` (metric filter, §6) | ≥1 summed over 1 day (matches the nightly cadence) | SNS on ALARM and OK | `journalctl -u karosl-backup.service`, or the `/karosl/staging/backup` log group for the `stage=...` reason; see `docs/S3_BACKUP_ARCHITECTURE.md` for the manual backup/restore fallback. |

`disk_used_percent` and `BackupFailures` use `treat_missing_data`: `breaching` for disk (silence from the
agent is itself worth flagging — it could mean the agent died), `notBreaching` for backup and the two EC2
metrics (their absence isn't informative the same way — e.g. backup's daily period means "no failure event
yet today" is the normal, expected state most of the day).

## 8. Notifications

SNS topic `karosl-staging-alerts` (`arn:aws:sns:eu-north-1:908877263055:karosl-staging-alerts`), one email
subscription (`grbsderrick@gmail.com`, pending the recipient's own click-to-confirm — AWS requires this,
nothing on our side can complete it). All four alarms publish on both `ALARM` and `OK` transitions, so a
recovery is visible too, not just the failure.

**Verified the SNS-publish path works mechanically**, independent of the subscription's confirmation state:
`aws cloudwatch set-alarm-state` was used to force `karosl-staging-backup-failed` to `ALARM` (the officially
supported way to test an alarm's actions without waiting for real threshold data), confirmed via
`describe-alarm-history` that the transition and its actions fired, then reset to `OK` afterward so the
dashboard doesn't show a stale test result. Actual email delivery cannot be confirmed until the subscription
is confirmed — that step needs the recipient, not this session.

## 9. Dashboard

`KarosL-Staging`, five widgets: EC2 CPU, EC2 status check, disk used %, backup successes vs. failures
(daily), and a combined alarm-status widget for all four alarms. Kept to one dashboard, one screen's worth
of widgets — CloudWatch's first 3 dashboards are free regardless, so cost wasn't the constraint; legibility
was.

## 10. Testing performed (Task 10) — all non-destructive

| Test | Method | Result |
|---|---|---|
| Django log delivery | Real `curl` to an authenticated endpoint with no token (401) | `WARNING ... Unauthorized: ...` appeared in `/karosl/staging/django` within ~15s |
| Nginx log delivery | Container recreate with the `awslogs` driver attached | Log stream created in `/karosl/staging/nginx`; `verify-staging.sh` stayed 12/12 throughout |
| Backup success delivery | Real `backup-to-s3.sh` run via `systemctl start karosl-backup.service` | `[EVENT] BACKUP_SUCCEEDED` reached `/karosl/staging/backup`; tee wrapper confirmed not to break `journalctl` |
| Backup failure delivery + metric | Forced `UPLOAD_FAILED` (nonexistent bucket) via the same systemd path | Event reached CloudWatch; `aws logs test-metric-filter` confirmed the pattern; `BackupFailures` metric showed `Sum=1` |
| SNS publish path | `set-alarm-state` forced `ALARM` on `karosl-staging-backup-failed` | Transition and actions confirmed via alarm history; reset to `OK` after |
| Live app unaffected | `verify-staging.sh` on both HTTPS paths after every infra change today | 12/12 throughout |

**Not tested, and why**: forcing `StatusCheckFailed` or sustained high `CPUUtilization` to their real ALARM
state would mean degrading the live pilot instance, which is explicitly out of bounds. Their *configuration*
was verified instead (`describe-alarms` shows correct thresholds/actions, state `INSUFFICIENT_DATA`→`OK` as
real EC2 metrics arrive) — this is an accepted testing limit, not a silently skipped check. Real email
delivery is blocked on the recipient confirming the SNS subscription.

## 11. Cost considerations (Task 11)

Qualitative, at this scale (single `t3.micro`, low request volume, small live pilot):

- **Log ingestion**: a handful of KB/day across three groups — Django WARNING+ only, nginx's normal
  traffic, backup's nightly run output. CloudWatch Logs ingestion is priced per GB; this deployment will not
  meaningfully approach even a fraction of a GB/month.
- **Log storage**: 14-day retention on all three groups keeps stored volume bounded and small.
- **Metrics**: `disk_used_percent`/`mem_used_percent` at 300s (5-minute) resolution, not the 1-minute
  "detailed monitoring" tier — deliberately standard-resolution, since nothing here needs sub-5-minute
  granularity. EC2's own `CPUUtilization`/`StatusCheckFailed` are the free basic-monitoring tier, already
  included.
- **Alarms**: 4 × ~$0.10/month each (standard resolution alarm pricing) — a few cents.
- **SNS**: email delivery is within the free tier at this volume (first 1,000 email notifications/month).
- **Dashboard**: one dashboard, within the first-3-free tier.

**Net estimate: comfortably under $2/month added**, dominated by the 4 alarms rather than log volume.
Avoided deliberately: high-resolution (1-minute) custom metrics, more than one dashboard, alarms beyond the
four listed, and any retention longer than the 14-day default.

## 12. Troubleshooting

- **A log group shows no recent events** — check the CloudWatch Agent is running:
  `sudo systemctl status amazon-cloudwatch-agent`; check its own log at
  `/opt/aws/amazon-cloudwatch-agent/logs/amazon-cloudwatch-agent.log` for `[outputs.cloudwatchlogs]`
  errors (commonly an IAM permission gap — verify with `aws sts get-caller-identity` from the instance,
  should report the role).
- **`disk_used_percent`/`mem_used_percent` alarm/dashboard shows no data despite the metric existing** — the
  real gotcha hit during setup: the CloudWatch Agent auto-tags these with `path`/`device`/`fstype`/`host`
  dimensions. A query or alarm without those exact dimensions matches nothing. Check
  `aws cloudwatch list-metrics --namespace KarosL/Staging` for the actual dimension set before writing a
  new alarm or widget against these metrics.
- **`BackupFailures`/`BackupSuccesses` not incrementing** — confirm the metric filter pattern with
  `aws logs test-metric-filter`; confirm the tee'd file exists and is growing
  (`tail -f ~/logs/karosl-backup.log` on the instance) — if it's empty, the systemd unit's `ExecStart`
  wrapper may not have been deployed (`systemctl cat karosl-backup.service` should show the `tee`-wrapped
  command).
- **An alarm won't leave `ALARM` state after a genuine transient issue clears** — alarms with
  `treat_missing_data: breaching` (only `disk_used_percent` here) stay in `ALARM` if the agent itself stops
  reporting, not just if the real value is high. Check the agent is alive before assuming the underlying
  problem persists.
- **No email arrives despite an alarm firing** — check the SNS subscription is `Confirmed`, not
  `PendingConfirmation`: `aws sns list-subscriptions-by-topic --topic-arn
  arn:aws:sns:eu-north-1:908877263055:karosl-staging-alerts`.

## 13. Files

New: `docker-compose.cloudwatch.yml`, `deploy/cloudwatch/cloudwatch-agent.json`,
`deploy/logrotate.d/karosl-backup`, this file. Edited: `deploy/systemd/karosl-backup.service` (tee wrapper).
AWS resources: 3 log groups, 2 metric filters, 4 alarms, 1 SNS topic + subscription, 1 dashboard, 1 IAM
inline policy — all listed above with exact names for `aws` CLI lookups.
