stdargs @ { scm, ... }:

scm.schema {
    guid = "S0HGKQEFHQ3HB7FI";
    name = "journal_ttls";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        <journals-S074SH7AQ51IC9DC>
    ];
}
