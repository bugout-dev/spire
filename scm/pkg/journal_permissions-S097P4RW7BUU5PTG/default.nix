stdargs @ { scm, ... }:

scm.schema {
    guid = "S097P4RW7BUU5PTG";
    name = "journal_permissions";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        <journals-S074SH7AQ51IC9DC>
        <spire_oauth_scopes-S0ZOWS3OK9R6MRT9>
    ];
}
