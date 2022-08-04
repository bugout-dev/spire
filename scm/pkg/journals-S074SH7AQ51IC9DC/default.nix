stdargs @ { scm, ... }:

scm.schema {
    guid = "S074SH7AQ51IC9DC";
    name = "journals";
    upgrade_sql = ./upgrade.sql;
    dependencies = [

    ];
}
