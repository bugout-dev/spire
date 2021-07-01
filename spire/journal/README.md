# Spire Journal

Journal API

### CLI

#### Journal handlers
* Get all journals
```bash
python -m spire.journal.cli journals get
```
* Get journal with specified `--name`
```bash
python -m spire.journal.cli journals get --name "Team journal: simiotics" | jq .
```

#### Journal permissions (holders) handlers
* Add new holder to journal with `--journal` as `journal_id`, `--holder` as `user_id`/`group_id`, `--type` as `user`/`group` and `--permissions` as list of possible permissions for journal `'journals.read, journals.update, journal.delete'`
```bash
python -m spire.journal.cli holders add --journal "<uuid>" --holder "<uuid>" --type "group" --permissions "journals.read, journals.u
pdate" | jq .
```
