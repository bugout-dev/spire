stdargs @ { scm, ... }:

scm.schema {
    guid = "S0JD4L40K2RY4QYJ";
    name = "github_issues_prs";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        <github_repos-S0HWDWZU388RCFJ0>
        <github_oauth_events-S0L8T3NBWKLZ66VR>
        <2022-08-09-github_issues_prs-R001CXQ8X5ATFOUE>
    ];
}
