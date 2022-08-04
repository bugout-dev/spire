stdargs @ { scm, ... }:

scm.schema {
    guid = "S0P2L5ZLC8Q7TTC6";
    name = "github_bugout_users";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        <github_oauth_events-S0L8T3NBWKLZ66VR>
    ];
}
