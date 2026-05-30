# cloud-project

Bronze AWS ingestion and silver normalization for Hacker News and X/Kaggle datasets.

## Prerequisites

- AWS CLI authenticated to the target account.
- Python 3.12 locally or in CI.
- GitHub repo secret: `AWS_ROLE_TO_ASSUME`.
- GitHub repo variables:
  - `AWS_REGION`, for example `eu-north-1`
  - `CFN_PROJECT_NAME`, default `cloud-computing-prj`
  - `CFN_ENVIRONMENT`, default `dev`
  - `HN_SCHEDULE_EXPRESSION`, default `cron(15 2 * * ? *)`
  - `AWSWRANGLER_LAYER_ARN`, awswrangler Lambda layer for your region (required for silver deploy)

Local shell defaults:

```bash
export AWS_REGION=eu-north-1
export PROJECT=cloud-computing-prj
export ENV=dev
```

## GitHub OIDC

Deploy once from your machine before GitHub Actions can deploy:

```bash
aws cloudformation deploy \
  --region "$AWS_REGION" \
  --stack-name "$PROJECT-$ENV-github-oidc" \
  --template-file infra/cloudformation/github-oidc.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    ProjectName="$PROJECT" \
    Environment="$ENV" \
    GitHubOrg="kize1509" \
    GitHubRepo="cloud-project" \
    GitHubBranch="main"
```

Set GitHub secret `AWS_ROLE_TO_ASSUME` to the stack output `RoleArn`.

## Deploy Everything

Push to `main`, or run the GitHub Action manually:

```text
Actions -> Deploy CloudFormation -> Run workflow
```

The workflow validates templates, runs tests, packages Lambdas, uploads artifacts, and deploys:

```text
infra/cloudformation/network.yaml
infra/cloudformation/storage.yaml
infra/cloudformation/bronze.yaml
infra/cloudformation/silver.yaml
```

### Manual AWS setup (silver)

1. Set GitHub variable `AWSWRANGLER_LAYER_ARN` to the [awswrangler Lambda layer ARN](https://aws-sdk-pandas.readthedocs.io/en/stable/install.html#aws-lambda-layer) for your Python 3.12 region.
2. Optional Discord webhook in SSM; set `DISCORD_WEBHOOK_PARAMETER_NAME` in GitHub variables.
3. Ensure bronze data exists before testing silver (HN invoke or X upload below). Silver Lambdas trigger automatically on new bronze S3 objects.

## Add A New Lambda

1. Add code:

```text
lambdas/bronze/<lambda_name>/app.py
```

2. Add a zip step in:

```text
scripts/package_lambdas.sh
```

3. Add CloudFormation resources in:

```text
infra/cloudformation/bronze.yaml
infra/cloudformation/silver.yaml
```

Include the Lambda role, log group, function, trigger, permission, and output.

4. Add/update tests in:

```text
tests/
```

5. Add artifact upload and deploy parameters in:

```text
.github/workflows/deploy.yml
```

## Deploy Lambda Changes

Preferred: push to `main` and let GitHub Actions deploy.

Manual deploy:

```bash
bash scripts/package_lambdas.sh build/lambda

ARTIFACT_BUCKET=$(aws cloudformation describe-stacks \
  --region "$AWS_REGION" \
  --stack-name "$PROJECT-$ENV-storage" \
  --query "Stacks[0].Outputs[?OutputKey=='ArtifactBucketName'].OutputValue" \
  --output text)

DATA_LAKE_BUCKET=$(aws cloudformation describe-stacks \
  --region "$AWS_REGION" \
  --stack-name "$PROJECT-$ENV-storage" \
  --query "Stacks[0].Outputs[?OutputKey=='DataLakeBucketName'].OutputValue" \
  --output text)

STAMP=$(date +%Y%m%d%H%M%S)
HN_KEY="lambda-artifacts/manual/$STAMP/hackernews_ingest.zip"
X_KEY="lambda-artifacts/manual/$STAMP/x_ingest.zip"

aws s3 cp build/lambda/hackernews_ingest.zip "s3://$ARTIFACT_BUCKET/$HN_KEY"
aws s3 cp build/lambda/x_ingest.zip "s3://$ARTIFACT_BUCKET/$X_KEY"

aws cloudformation deploy \
  --region "$AWS_REGION" \
  --stack-name "$PROJECT-$ENV-bronze" \
  --template-file infra/cloudformation/bronze.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides \
    ProjectName="$PROJECT" \
    Environment="$ENV" \
    AwsRegion="$AWS_REGION" \
    DataLakeBucketName="$DATA_LAKE_BUCKET" \
    BronzePrefix="bronze" \
    DiscordWebhookParameterName="" \
    HnScheduleExpression="cron(15 2 * * ? *)" \
    HnTargetDayOffset="1" \
    HackerNewsLambdaS3Bucket="$ARTIFACT_BUCKET" \
    HackerNewsLambdaS3Key="$HN_KEY" \
    XLambdaS3Bucket="$ARTIFACT_BUCKET" \
    XLambdaS3Key="$X_KEY"
```

## Add Template Configuration

Add or edit CloudFormation in:

```text
infra/cloudformation/<name>.yaml
```

Then update:

```text
.github/workflows/deploy.yml
```

Add the template to validation and add a deploy step if it is a new stack.

## Deploy Infra Changes

Preferred: push to `main` and let GitHub Actions deploy.

Manual single-stack deploy:

```bash
aws cloudformation deploy \
  --region "$AWS_REGION" \
  --stack-name "$PROJECT-$ENV-<stack>" \
  --template-file infra/cloudformation/<stack>.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameter-overrides ProjectName="$PROJECT" Environment="$ENV"
```

Use `--capabilities CAPABILITY_NAMED_IAM` only for templates that create named IAM resources.

## Test Bronze

Get the bucket:

```bash
DATA_LAKE_BUCKET=$(aws cloudformation describe-stacks \
  --region "$AWS_REGION" \
  --stack-name "$PROJECT-$ENV-storage" \
  --query "Stacks[0].Outputs[?OutputKey=='DataLakeBucketName'].OutputValue" \
  --output text)
```

### Hacker News

Invoke:

```bash
aws lambda invoke \
  --region "$AWS_REGION" \
  --function-name "$PROJECT-$ENV-hackernews-bronze-ingest" \
  --cli-binary-format raw-in-base64-out \
  --payload '{"target_date":"2026-05-28"}' \
  response.json
```

Observe:

```bash
aws s3 ls "s3://$DATA_LAKE_BUCKET/bronze/hackernews/year=2026/month=05/day=28/"
aws logs tail "/aws/lambda/$PROJECT-$ENV-hackernews-bronze-ingest" --region "$AWS_REGION" --since 20m
```

Scheduled run:

```text
Wait until HN_SCHEDULE_EXPRESSION fires.
Observe bronze/hackernews/year=YYYY/month=MM/day=DD/items.json
```

### X Uploads

Bitcoin upload here:

```bash
printf 'id,text\n1,hello bitcoin\n' > /tmp/bitcoin.csv
aws s3 cp /tmp/bitcoin.csv "s3://$DATA_LAKE_BUCKET/incoming/x/bitcoin-tweets/bitcoin.csv"
```

Observe here:

```bash
aws s3 ls "s3://$DATA_LAKE_BUCKET/bronze/x/bitcoin-tweets/raw/bitcoin.csv"
aws logs tail "/aws/lambda/$PROJECT-$ENV-x-bronze-ingest" --region "$AWS_REGION" --since 20m
```

Covid upload here:

```bash
printf 'id,text\n1,hello covid\n' > /tmp/covid.csv
aws s3 cp /tmp/covid.csv "s3://$DATA_LAKE_BUCKET/incoming/x/covid-tweets/covid.csv"
```

Observe here:

```bash
aws s3 ls "s3://$DATA_LAKE_BUCKET/bronze/x/covid-tweets/raw/covid.csv"
aws logs tail "/aws/lambda/$PROJECT-$ENV-x-bronze-ingest" --region "$AWS_REGION" --since 20m
```

## Test Silver

Silver runs automatically when bronze files land in S3. To backfill existing bronze data, re-run bronze (HN invoke or re-upload X CSV to `incoming/x/...`).

### Verify Parquet output

```bash
aws s3 ls "s3://$DATA_LAKE_BUCKET/silver/posts/" --recursive
aws s3 ls "s3://$DATA_LAKE_BUCKET/silver/users/" --recursive
aws logs tail "/aws/lambda/$PROJECT-$ENV-hackernews-silver-normalize" --region "$AWS_REGION" --since 30m
aws logs tail "/aws/lambda/$PROJECT-$ENV-x-silver-normalize" --region "$AWS_REGION" --since 30m
```

### Manual silver deploy

After packaging Lambdas, deploy the silver stack with the same artifact bucket keys used for bronze:

```bash
bash scripts/package_lambdas.sh build/lambda

# Upload all four zips, then deploy silver.yaml with AwswranglerLayerArn=...
# See deploy.yml silver stack step for full parameter list.
```

## Local Checks

```bash
python3 -m unittest discover -s tests
bash scripts/package_lambdas.sh build/lambda
```
