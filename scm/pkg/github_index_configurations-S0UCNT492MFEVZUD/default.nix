stdargs @ { scm, ... }:

scm.schema {
    guid = "S0UCNT492MFEVZUD";
    name = "github_index_configurations";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        <github_oauth_events-S0L8T3NBWKLZ66VR>
        <2022-08-09-github_index_configurations-R001CXQC7NOUFH7O>
    ];
}
