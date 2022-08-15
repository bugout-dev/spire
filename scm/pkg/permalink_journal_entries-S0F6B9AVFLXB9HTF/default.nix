stdargs @ { scm, ... }:

scm.schema {
    guid = "S0F6B9AVFLXB9HTF";
    name = "permalink_journal_entries";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        <2022-08-09-permalink_journal_entries-R001CXOGMR42NRG2>
    ];
}
