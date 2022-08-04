stdargs @ { scm, ... }:

scm.schema {
    guid = "S0HWDWZU388RCFJ0";
    name = "github_repos";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        <github_oauth_events-S0L8T3NBWKLZ66VR>
    ];
}
