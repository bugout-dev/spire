stdargs @ { scm, ... }:

scm.revision {
    guid = "R001CXOC045GKTF4";
    name = "2022-08-09-public_journals";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        <2022-08-09-public_users-R001CXOB6OVUS12Q>
    ];
}
