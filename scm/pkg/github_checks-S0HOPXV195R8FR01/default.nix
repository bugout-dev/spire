stdargs @ { scm, ... }:

scm.schema {
    guid = "S0HOPXV195R8FR01";
    name = "github_checks";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        <github_oauth_events-S0L8T3NBWKLZ66VR>
        <github_issues_prs-S0JD4L40K2RY4QYJ>
        <github_repos-S0HWDWZU388RCFJ0>
    ];
}
