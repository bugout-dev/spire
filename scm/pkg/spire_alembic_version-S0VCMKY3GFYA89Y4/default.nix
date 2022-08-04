stdargs @ { scm, ... }:

scm.schema {
    guid = "S0VCMKY3GFYA89Y4";
    name = "spire_alembic_version";
    upgrade_sql = ./upgrade.sql;
    dependencies = [

    ];
}
