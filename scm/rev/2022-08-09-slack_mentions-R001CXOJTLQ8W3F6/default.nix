stdargs @ { scm, ... }:

scm.revision {
    guid = "R001CXOJTLQ8W3F6";
    name = "2022-08-09-slack_mentions";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        <2022-08-09-slack_oauth_events-R001CXOHUMYQRMW3>
    ];
}
