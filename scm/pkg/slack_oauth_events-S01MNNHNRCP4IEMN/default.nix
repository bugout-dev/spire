stdargs @ { scm, ... }:

scm.schema {
    guid = "S01MNNHNRCP4IEMN";
    name = "slack_oauth_events";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        <2022-08-09-slack_oauth_events-R001CXOHUMYQRMW3>
    ];
}
