stdargs @ { scm, ... }:

scm.schema {
    guid = "S0VCMKY3GFYA89Y4";
    name = "spire_alembic_version";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        <2022-08-09-spire_alembic_version-R001CXO9ZI9ARITB>
    ];
}
