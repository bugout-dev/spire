stdargs @ { scm, ... }:

scm.schema {
    guid = "S01ALIK59MFP5AT1";
    name = "public_journals";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        <public_users-S07LZWVWCRX5RHBY>
    ];
}
