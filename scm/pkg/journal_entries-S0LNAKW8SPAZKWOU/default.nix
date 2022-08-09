stdargs @ { scm, ... }:

scm.schema {
    guid = "S0LNAKW8SPAZKWOU";
    name = "journal_entries";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        <journals-S074SH7AQ51IC9DC>
        <2022-08-04-journal_entries-R001COSJY6KVDFEJ>
    ];
}
