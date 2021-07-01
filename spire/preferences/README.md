## Spire Preferences API

All requests to these endpoints are authenticated using the standard mechanisms.

### default_journal

Stores a user's default journal (to be synchronized across all clients).

#### Setting a user's default journal

```bash
curl -X PUT \
    -H "Authorization: Bearer <token>" \
    https://spire.bugout.dev/preferences/default_journal \
    -d "{\"id\": \"<journal_id>\"}"
```

#### Getting a user's default journal

```bash
curl -H "Authorization: Bearer <token>" https://spire.bugout.dev/preferences/default_journal
```

Response is a JSON object with the following structure:

```json
{
  "id": "<journal_id>"
}
```

#### Deleting (unsetting) a user's default journal

```bash
curl -X DELETE -H "Authorization: Bearer <token>" https://spire.bugout.dev/preferences/default_journal
```

#### Errors

- 403 status code if request is not authenticated
- 423 status code if the preference is locked (because it is being set by another client) (on `POST`, `PUT`, `DELETE` requests)
