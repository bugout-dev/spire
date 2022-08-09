stdargs @ { scm, ... }:

scm.revision {
    guid = "R001CXOLFSZXCSY4";
    name = "2022-08-09-slack_bugout_users";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        <2022-08-09-slack_oauth_events-R001CXOHUMYQRMW3>
    ];
}
