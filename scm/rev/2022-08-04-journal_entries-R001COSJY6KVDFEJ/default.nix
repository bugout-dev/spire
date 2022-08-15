stdargs @ { scm, ... }:

scm.revision {
    guid = "R001COSJY6KVDFEJ";
    name = "2022-08-04-journal_entries";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        <2022-08-04-journals-R001COSILGN1FVM0>
    ];
}
