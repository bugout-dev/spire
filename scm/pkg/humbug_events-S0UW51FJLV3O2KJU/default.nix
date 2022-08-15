stdargs @ { scm, ... }:

scm.schema {
    guid = "S0UW51FJLV3O2KJU";
    name = "humbug_events";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        <2022-08-09-humbug_events-R001CXOMEZARH1I7>
    ];
}
