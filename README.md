# Spire

Bugout custom knowledge bases

### Setup:
* Clone git repository
* Install postgresql (https://www.postgresql.org/download/linux/ubuntu/)
* Install elasticsearch (https://www.elastic.co/guide/en/elasticsearch/reference/7.9/deb.html)
* Install requirements
* Create dev version and manage app at https://api.slack.com/apps/
* Copy sample.env to dev.env and fill `dev` fields
```
export BUGOUT_SLACK_[your info for slack apps]
...
export SPIRE_DB_URI="postgresql://postgres:postgres@localhost/brood_dev"
export ELASTICSEARCH_[your info for elasticsearch]
...
export BUGOUT_JOURNAL_EMOJI="beetle"
export SPIRE_API_URL="http://0.0.0.0:7475"
export BUGOUT_AUTH_URL="http://localhost:7474"
```
* Copy `alembic.sample.ini` to `alembic.dev.ini` and correct field
```
sqlalchemy.url = postgresql://postgres:postgres@localhost/brood_dev
```
* Run alembic migration
```
> ./alembic.sh -c alembic.dev.ini upgrade head
```
* Install ngrok (https://ngrok.com/download)
* Run ngrok tunnel
```
> ngrok http 7475
```
* Run server
```
> ./dev.sh
```
* Set slack `OAuth & Permissions` Redirect URLs to ngrok
```
https://60843a634907.ngrok.io/slack/oauth
```
* Add OAuth Scopes
```
app_mentions:read
channels:history
channels:read
chat:write
commands
emoji:read
groups:history
groups:read
im:history
im:write
links:read
mpim:history
reactions:read
reactions:write
users.profile:read
```
* Set slack `Event Subscriptions` Request URL to ngrok
```
https://60843a634907.ngrok.io/slack/event
```
* Add events
```
app_mentions
app_uninstalled
channel_rename
emoji_changed
link_shared
message.im
reaction_added
reaction_removed
```
* Run brood local server
* Create brood user `slack_installation` with hard password (this user will be managing 
whole slack workspaces), generate token for this user and add it to environment at `dev.env`
```
export BUGOUT_INSTALLATION_TOKEN="<installation user token from brood>"
```
* Add slack dev bot to slack

* For Shortcuts use readme (https://github.com/simiotics/spire/blob/bug-9-visual-slack-search/spire/slack/shortcuts.md)
