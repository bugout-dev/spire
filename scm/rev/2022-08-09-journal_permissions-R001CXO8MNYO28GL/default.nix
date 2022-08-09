stdargs @ { scm, ... }:

scm.revision {
    guid = "R001CXO8MNYO28GL";
    name = "2022-08-09-journal_permissions";
    upgrade_sql = ./upgrade.sql;
    dependencies = [
        <2022-08-09-spire_oauth_scopes-R001CXO7K06P4BAK>
        <2022-08-04-journals-R001COSILGN1FVM0>
    ];
}
