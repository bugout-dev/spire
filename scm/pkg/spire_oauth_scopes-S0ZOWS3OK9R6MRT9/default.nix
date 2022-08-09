stdargs @ { scm, ... }:

scm.schema {
    guid = "S0ZOWS3OK9R6MRT9";
    name = "spire_oauth_scopes";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        <2022-08-09-spire_oauth_scopes-R001CXO7K06P4BAK>
    ];
}
