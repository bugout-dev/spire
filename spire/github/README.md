# Spire GitHub Integration

### Create GitHub app
* Go to organization settings and choose GitHub App
* Generate all secrets and keys
* Set Permissions
```
Actions: Read-only
Checks: Read & write
Contents: Read-only
Issues: Read & write
Metadata: Read-only
Pull requests: Read & write
Webhooks: Read-only
Commit statuses: Read-only
```
* Subscribe to events
```
Create
Checks
Issue comment
Label
Push
Commit comment
Delete
Issues
Pull request
Pull request review comment
Release
``` 

### Setup Spire
* Update dev.env
```
export AWS_S3_GITHUB_SUMMARY_BUCKET="bugout-locust-summaries"
export AWS_S3_GITHUB_SUMMARY_PREFIX="dev/github/summary"
...
export BUGOUT_GITHUB_APP_ID="<github app id>"
export BUGOUT_GITHUB_CLIENT_ID="<github client id>"
export BUGOUT_GITHUB_CLIENT_SECRET="<github client secret>"
export BUGOUT_GITHUB_PRIVATE_KEY_FILE="<path to .pem file>"
export BUGOUT_GITHUB_WEBHOOK_SECRET="<randomly generated uuid>"
export BUGOUT_GITHUB_PRIVATE_KEY_BASE64="<BUGOUT_GITHUB_PRIVATE_KEY_FILE converted to base64>"
export GITHUB_BOT_USERNAME="bugout-dev"
```
* You can generate BUGOUT_GITHUB_PRIVATE_KEY_BASE64 by command
```
base64 -w0 bugout-dev.2020-11-10.private-key.pem
```
* Run alembic migration `added_github_oauth_model`
* Run ngrok
* Change links at GitHub App settings
* Run server

### Install Bugout GitHub Bot
* Got to page https://github.com/apps/bug-kompotkot-app
* Press Install and chose you Organization
* With `spire.github.cli` generate Bugout secret for installed installation
* Add Bugout secret

### Github Action yml for target Repository
* Add in your Repository GitHub Action file `.github/workflows/locust.yml`
* Change link to ngrok
```yaml
name: Locust summary

on: [pull_request_target]

jobs:
  build:
    runs-on: ubuntu-20.04
    steps:
      - name: PR head repo
        id: head_repo_name
        run: |
          HEAD_REPO_NAME=$(jq -r '.pull_request.head.repo.full_name' "$GITHUB_EVENT_PATH")
          echo "PR head repo: $HEAD_REPO_NAME"
          echo "::set-output name=repo::$HEAD_REPO_NAME"
      - name: Checkout git repo
        uses: actions/checkout@v2
        with:
          repository: ${{ steps.head_repo_name.outputs.repo }}
          fetch-depth: 0
      - name: Install python
        uses: actions/setup-python@v2
        with:
          python-version: "3.8"
      - name: Install dependencies
        run: |
          python -m pip install --upgrade pip setuptools
          pip install bugout-locust
      - name: Generate and send Locust summary
        env:
          BUGOUT_SECRET: ${{ secrets.BUGOUT_SECRET }}
        run: |
          locust.github publish

```
* Make Commit and open Pull Request

### CLI
* List all installations, it github repo info, id and bugout secrets
```
python -m spire.github.cli list
```
* Update github oauth token. This command refreshes all tokens with less than 5 minutes left to live. With `spiregithubtoken.timer` this commands runs each 2 minutes to find and update pre-dead tokens.
```
python -m spire.github.cli update
```
