stdargs @ { scm, ... }:

scm.schema {
    guid = "S00VNGQH2U6QXSF3";
    name = "slack_index_configurations";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        <slack_oauth_events-S01MNNHNRCP4IEMN>
        <2022-08-09-slack_index_configurations-R001CXOIRAGB6I2B>
    ];
}
