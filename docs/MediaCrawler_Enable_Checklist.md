# MediaCrawler Enable Checklist

This checklist is an approval gate. Completing the preparation phase does not
enable the Scheduler or change `schedule_enabled`.

- [ ] scheduler profile ready and independently provisioned
- [ ] runtime command and Python entry verified by read-only check
- [ ] `MEDIA_CRAWLER_REAL_RUN_GATE` approval recorded and changed only in the
      explicit enable phase
- [ ] schedule window approved (`schedule_interval_minutes=60`)
- [ ] rollback plan documented and tested at the change-control level

Current preparation state:

```text
MEDIA_CRAWLER_REAL_RUN_GATE=false
DataSource.schedule_enabled=false
Scheduler=Disabled
```
