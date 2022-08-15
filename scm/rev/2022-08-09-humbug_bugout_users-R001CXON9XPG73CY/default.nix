stdargs @ { scm, ... }:

scm.revision {
    guid = "R001CXON9XPG73CY";
    name = "2022-08-09-humbug_bugout_users";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        <2022-08-09-humbug_events-R001CXOMEZARH1I7>
    ];
}
