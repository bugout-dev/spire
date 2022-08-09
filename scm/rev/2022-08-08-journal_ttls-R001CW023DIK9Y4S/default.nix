stdargs @ { scm, ... }:

scm.revision {
    guid = "R001CW023DIK9Y4S";
    name = "2022-08-08-journal_ttls";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        <2022-08-04-journals-R001COSILGN1FVM0>
    ];
}
