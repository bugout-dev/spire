stdargs @ { scm, ... }:

scm.revision {
    guid = "R001CW00WFRTKUAV";
    name = "2022-08-08-journal_entry_tags";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        <2022-08-04-journal_entries-R001COSJY6KVDFEJ>
    ];
}
