stdargs @ { scm, ... }:

scm.schema {
    guid = "S0WZY9D1KCP4I5SI";
    name = "slack_bugout_users";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        <slack_oauth_events-S01MNNHNRCP4IEMN>
        <2022-08-09-slack_bugout_users-R001CXOLFSZXCSY4>
    ];
}
