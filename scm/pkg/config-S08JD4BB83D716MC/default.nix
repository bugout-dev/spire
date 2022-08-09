stdargs @ { scm, ... }:

scm.schema {
    guid = "S08JD4BB83D716MC";
    name = "config";
    upgrade_sql = ./upgrade.sql;
    basefiles = ./basefiles;
    dependencies = [
        <2022-08-09-config-R001CXSS088216AS>
    ];
}

