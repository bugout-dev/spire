stdargs @ { scm, ... }:

scm.revision {
    guid = "R001CXQFBBPJ8HNZ";
    name = "2022-08-09-github_check_notes";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        <2022-08-09-github_checks-R001CXQDMIDE091L>
    ];
}
