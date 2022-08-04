stdargs @ { scm, ... }:

scm.schema {
    guid = "S0BIVC6QGPEGMSFO";
    name = "enums";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        ./rev/2022-08-04-enums-R001COR9HNMDUY05
    ];
}
