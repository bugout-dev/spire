stdargs @ { scm, ... }:

scm.schema {
    guid = "S02X88WPG64848AU";
    name = "journal_entry_tags";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        <journal_entries-S0LNAKW8SPAZKWOU>
    ];
}
