stdargs @ { scm, ... }:

scm.schema {
    guid = "S07LZWVWCRX5RHBY";
    name = "public_users";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        <2022-08-09-public_users-R001CXOB6OVUS12Q>
    ];
}
