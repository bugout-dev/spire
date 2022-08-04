stdargs @ { scm, ... }:

scm.schema {
    guid = "S07LZWVWCRX5RHBY";
    name = "public_users";
    upgrade_sql = ./upgrade.sql;
    dependencies = [

    ];
}
