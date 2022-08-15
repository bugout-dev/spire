stdargs @ { scm, ... }:

scm.revision {
    guid = "R001CXOO2SHCU5OF";
    name = "2022-08-09-humbug_bugout_user_tokens";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        <2022-08-09-humbug_events-R001CXOMEZARH1I7>
        <2022-08-09-humbug_bugout_users-R001CXON9XPG73CY>
    ];
}
