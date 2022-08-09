stdargs @ { scm, ... }:

scm.schema {
    guid = "S0Y5YX0NO0X14XMJ";
    name = "preferences_default_journals";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        <2022-08-09-preferences_default_journals-R001CXOCZRHVFVO2>
    ];
}
