stdargs @ { scm, ... }:

scm.revision {
    guid = "R001CXOIRAGB6I2B";
    name = "2022-08-09-slack_index_configurations";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        <2022-08-09-slack_oauth_events-R001CXOHUMYQRMW3>
    ];
}
