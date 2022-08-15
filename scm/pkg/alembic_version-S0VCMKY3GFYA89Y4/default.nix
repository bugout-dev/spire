stdargs @ { scm, ... }:

scm.schema {
    guid = "S0VCMKY3GFYA89Y4";
    name = "alembic_version";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        <2022-08-09-alembic_version-R001CXO9ZI9ARITB>
    ];
}
