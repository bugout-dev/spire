stdargs @ { scm, ... }:

scm.schema {
    guid = "S00VNGQH2U6QXSF3";
    name = "slack_index_configurations";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        <slack_oauth_events-S01MNNHNRCP4IEMN>
    ];
}
