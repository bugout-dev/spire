stdargs @ { scm, ... }:

scm.schema {
    guid = "S0CQ9TSU7QG4T20R";
    name = "permalink_journals";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        <2022-08-09-permalink_journals-R001CXODPVGLEDUS>
    ];
}
