stdargs @ { scm, ... }:

scm.schema {
    guid = "S01ALIK59MFP5AT1";
    name = "public_journals";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        <public_users-S07LZWVWCRX5RHBY>
        <2022-08-09-public_journals-R001CXOC045GKTF4>
    ];
}
