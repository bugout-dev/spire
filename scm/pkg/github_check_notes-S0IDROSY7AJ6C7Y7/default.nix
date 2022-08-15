stdargs @ { scm, ... }:

scm.schema {
    guid = "S0IDROSY7AJ6C7Y7";
    name = "github_check_notes";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        <github_checks-S0HOPXV195R8FR01>
        <2022-08-09-github_check_notes-R001CXQFBBPJ8HNZ>
    ];
}
