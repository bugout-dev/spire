stdargs @ { scm, ... }:

scm.revision {
    guid = "R001CXOGMR42NRG2";
    name = "2022-08-09-permalink_journal_entries";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        
    ];
}
