stdargs @ { scm, ... }:

scm.schema {
    guid = "S0HK79615Y9EYZGU";
    name = "github_diffs";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        <2022-08-09-github_diffs-R001CXQCZ07VEAFY>
    ];
}
