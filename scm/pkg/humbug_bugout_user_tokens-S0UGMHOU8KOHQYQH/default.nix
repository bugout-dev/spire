stdargs @ { scm, ... }:

scm.schema {
    guid = "S0UGMHOU8KOHQYQH";
    name = "humbug_bugout_user_tokens";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        <humbug_events-S0UW51FJLV3O2KJU>
        <humbug_bugout_users-S0GV5K48XQRIGJND>
        <2022-08-09-humbug_bugout_user_tokens-R001CXOO2SHCU5OF>
    ];
}
