stdargs @ { scm, ... }:

scm.schema {
    guid = "S02YUYT8BPR2769M";
    name = "slack_mentions";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        <slack_oauth_events-S01MNNHNRCP4IEMN>
        <2022-08-09-slack_mentions-R001CXOJTLQ8W3F6>
    ];
}
