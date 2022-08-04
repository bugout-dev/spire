stdargs @ { scm, ... }:

scm.schema {
    guid = "S0Y5YX0NO0X14XMJ";
    name = "preferences_default_journals";
    upgrade_sql = ./upgrade.sql;
    dependencies = [

    ];
}
