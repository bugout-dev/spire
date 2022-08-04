stdargs @ { scm, ... }:

scm.schema {
    guid = "S0GV5K48XQRIGJND";
    name = "humbug_bugout_users";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        <humbug_events-S0UW51FJLV3O2KJU>
    ];
}
