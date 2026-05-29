# Project Specification — Računarstvo u oblaku

> Source: `Specifikacija projekta.pdf`  
> Audience: agents and developers implementing this project

## Overview

Build an AWS-based platform for **collecting, processing, storing, and analyzing** data from social networks and blog portals.

**Hard requirements:**
- Must run on **AWS**
- Data processing design must follow **Medallion architecture** (bronze → silver → gold)
- All infrastructure must be defined as **Infrastructure as Code** (CloudFormation) — elimination criterion; projects without IaC will not be reviewed

**Data sources (exactly 2):**
1. **Hacker News** — live ingestion via API (Lambda)
2. **X (Twitter)** — both Kaggle datasets: Bitcoin Tweets + Covid Tweets (see [Project Decisions](#project-decisions))

---

## Project Decisions

These choices are **locked in** for this implementation:

| Area | Decision |
|------|----------|
| **IaC tool** | [CloudFormation](https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/Welcome.html) |
| **Notifications** | [Discord](https://discord.com/) webhook on job failure (SSM Parameter Store) |
| **X data source** | Both spec-provided Kaggle datasets — **no X API** |

**X datasets in use:**
- [Bitcoin Tweets](https://www.kaggle.com/datasets/kaushiksuresh147/bitcoin-tweets)
- [Covid Tweets](https://www.kaggle.com/datasets/gpreda/covid19-tweets)

---

## Architecture

### Medallion layers

| Layer | Purpose | Format | Storage |
|-------|---------|--------|---------|
| Bronze | Raw ingestion, no transformation | Original (csv, json, xml, etc.) | S3 |
| Silver | Normalization, schema, deduplication | Parquet (partitioned) | S3 |
| Gold | Metrics and KPIs | Parquet (partitioned) | S3 → PostgreSQL |

Reference: [Medallion architecture](https://www.databricks.com/glossary/medallion-architecture)

### Pipeline diagram

```
Hacker News ──► Lambda (scheduled) ──► bronze/hackernews/...           [bronze]
X upload ──► incoming/x/ ──► Lambda ──► bronze/x/.../raw/...          [bronze]
                                    │
                                    ▼
                              Lambda: Normalizuje podatke
                                    │
                                    ▼
                         S3: Normalizovani podaci (parquet)          [silver]
                                    │
                                    ▼
                              Lambda: Transformiše podatke
                                    │
                                    ▼
                         S3: Transformisani podaci (parquet)         [gold]
                                    │
                                    ▼
                    Lambda: Premešta podatke u PostgreSQL bazu
                                    │
                                    ▼
                    EC2: PostgreSQL + Apache Superset
```

**Optional orchestration:** AWS Step Functions may be used to split normalization and transformation into multiple Lambda steps, simplifying each function's implementation.

### Repository layout

```
infra/cloudformation/     # network, storage, bronze, github-oidc stacks
lambdas/bronze/           # hackernews_ingest, x_ingest
scripts/package_lambdas.sh
tests/
.github/workflows/deploy.yml
```

**CloudFormation stacks (deploy order):** `network` → `storage` → `bronze`  
**Defaults:** `ProjectName=cloud-computing-prj`, `Environment=dev`, `AWS_REGION=eu-north-1`

**S3 buckets:**
- Data lake: `{ProjectName}-{Environment}-{AccountId}-{Region}-data-lake`
- Artifacts (Lambda zips): `{ProjectName}-{Environment}-{AccountId}-{Region}-artifacts`

**Data lake prefixes:** `bronze/`, `silver/`, `gold/`, `incoming/x/`

---

## References

| Topic | URL |
|-------|-----|
| Medallion architecture | https://www.databricks.com/glossary/medallion-architecture |
| Hacker News | https://news.ycombinator.com/ |
| Hacker News API | https://github.com/HackerNews/API |
| HN Search API (optional helper) | https://hn.algolia.com/api |
| X (Twitter) | https://x.com/ |
| Example X dataset — Bitcoin Tweets | https://www.kaggle.com/datasets/kaushiksuresh147/bitcoin-tweets |
| Example X dataset — Covid Tweets | https://www.kaggle.com/datasets/gpreda/covid19-tweets |
| Parquet format | https://parquet.apache.org/ |
| awswrangler library | https://aws-sdk-pandas.readthedocs.io/en/stable/ |
| awswrangler Lambda layer | https://aws-sdk-pandas.readthedocs.io/en/stable/install.html#aws-lambda-layer |
| Parquet partitioning example | https://aws-sdk-pandas.readthedocs.io/en/stable/tutorials/004%20-%20Parquet%20Datasets.html#Creating-a-Partitioned-Dataset |
| Star schema (gold layer design) | https://www.databricks.com/glossary/star-schema |
| Apache Superset | https://superset.apache.org/ |
| CloudFormation (IaC) | https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/Welcome.html |
| Terraform | https://www.hashicorp.com/products/terraform |
| AWS CDK | https://docs.aws.amazon.com/cdk/v2/guide/home.html |
| Terragrunt | https://terragrunt.gruntwork.io/ |

---

## Functional Requirements

### 1. Data collection — bronze layer (10 pts)

Collect data from **Hacker News** and **X (Twitter)**.

#### 1.1 Hacker News

Hacker News is a portal for blogs, news, and comments on various topics.

**Daily ingestion:** collect all items created the previous day:
- stories
- asks
- comments
- jobs
- polls

**Implementation:**
- Lambda: `lambdas/bronze/hackernews_ingest/` (Python 3.12)
- Trigger: EventBridge Scheduler — default `cron(15 2 * * ? *)` (02:15 UTC daily)
- API: HN Firebase API (`https://hacker-news.firebaseio.com/v0`); docs: https://github.com/HackerNews/API
- Collects previous UTC day (`HN_TARGET_DAY_OFFSET=1`); manual invoke accepts `{"target_date":"YYYY-MM-DD"}`
- Output: single raw JSON array per day — no processing or transformation
- **S3 path:** `bronze/hackernews/year=YYYY/month=MM/day=DD/items.json`

**Optional helper:** HN Search API (keyword search): https://hn.algolia.com/api

#### 1.2 X (Twitter)

X is a social network for short posts.

Use **both** Kaggle datasets — do **not** call the X API.

**Datasets (both required):**
- [Bitcoin Tweets](https://www.kaggle.com/datasets/kaushiksuresh147/bitcoin-tweets)
- [Covid Tweets](https://www.kaggle.com/datasets/gpreda/covid19-tweets)

**Implementation:**
- Download datasets locally; upload files to staging prefix `incoming/x/{dataset}/`
- Lambda: `lambdas/bronze/x_ingest/` (Python 3.12)
- Trigger: S3 `Object Created` under `incoming/x/` (EventBridge)
- Server-side S3 copy to bronze — **no normalization or transformation**; preserve original format
- **Supported datasets:** `bitcoin-tweets`, `covid-tweets`
- **Path mapping:** `incoming/x/{dataset}/{file}` → `bronze/x/{dataset}/raw/{file}`

---

### 2. Data normalization — silver layer (14 pts)

Bronze data may be in different formats with different structures. Normalize to a **single format** and define a **data schema**. Without a schema, downstream queries cannot be written reliably.

Implement a **Lambda function (or functions)** for normalization.

#### Normalization must include

- **Flatten nested structures** — e.g. `kids` fields in Hacker News posts
- **Align timestamps** — Hacker News uses Unix Epoch (`1736978058`); X uses ISO-8601 (`2026-01-15T21:54:18Z`). Normalize to a single **UTC** format
- **Clean values** — e.g. strip HTML tags (`<p>`, `<i>`) from Hacker News content
- **Remove duplicates**
- **Any additional processing** you deem necessary beyond the above
- **Establish schema** — define tables (dataframes) with columns and relationships

**Schema rules:**
- Minimize redundancy; aim for **3NF**
- Save tables as **Parquet**, **partitioned**
- Schema is **not fixed** — it may evolve if deficiencies are found; choose structure based on what data is useful

**Recommended library:** [awswrangler](https://aws-sdk-pandas.readthedocs.io/en/stable/) (+ [Lambda layer](https://aws-sdk-pandas.readthedocs.io/en/stable/install.html#aws-lambda-layer))  
**Partitioning example:** https://aws-sdk-pandas.readthedocs.io/en/stable/tutorials/004%20-%20Parquet%20Datasets.html#Creating-a-Partitioned-Dataset

#### Example schema (2 tables)

**`users`**

| Column | Type | Description |
|--------|------|-------------|
| `user_id` | UUID | Generated ID |
| `username` | String | From Hacker News or X |
| `platform` | String | `'Hacker News'` or `'X'` |
| `karma_score` | Integer | Hacker News reputation; `null` for X users |
| `is_verified` | Boolean | X verification status; `null` for Hacker News users |
| `created_at` | Timestamp | Normalized UTC ISO-8601 |

**`posts`**

| Column | Type | Description |
|--------|------|-------------|
| `post_id` | String | Original ID from Hacker News or X |
| `author_username` | String | FK to `users.username` |
| `content_text` | String | Post content; HTML tags cleaned |
| `created_at` | Timestamp | Normalized UTC ISO-8601 |
| `post_type` | String | `'story'`, `'comment'`, `'tweet'`, `'retweet'`, etc. |

#### Example silver S3 layout

```
s3://social-medias/silver/
├── posts/
│   └── year=2026/month=01/day=15/
│       └── data_001.parquet
└── users/
    ├── platform=HackerNews/
    └── platform=X/
```

**Partitioning:**
- `users` → by `platform`
- `posts` → by timestamp (e.g. `year/month/day`)

---

### 3. Data transformation — gold layer (10 pts)

Implement a **Lambda function (or functions)** that transforms silver data into **metrics and KPIs**.

#### Metrics to compute

- Daily count on Hacker News of: stories, asks, comments, jobs, polls
- Daily count of Hacker News users
- Daily count of X users
- Top 10 X users by follower count
- Top 10 Hacker News users by karma score (daily)
- Bottom 10 Hacker News users by karma score (daily)
- Top 10 Hacker News job postings by score (daily)
- Top 10 Hacker News posts by score (daily)

#### KPIs to compute

- **Data Quality Score** — percentage of rows in tables/dataframes that are non-null; indicates how well normalization was done

#### Gold schema design

Use [Star Schema](https://www.databricks.com/glossary/star-schema) where appropriate.

**Example table: `daily_users_metric`**

| Column | Type | Description |
|--------|------|-------------|
| `date` | date | Date |
| `platform` | String | `'Hacker News'` or `'X'` |
| `total_users` | Integer | Total users on platform |
| `new_users` | Integer | New users registered that day on platform |

Example data:

| date | platform | total_users | new_users |
|------|----------|-------------|-----------|
| 2025-01-15 | Hacker News | 1500 | 100 |
| 2025-01-15 | X | 456 | 74 |
| 2025-01-16 | Hacker News | 12030 | 530 |
| 2025-01-16 | X | 523 | 87 |

#### Example gold S3 layout

```
s3://social-medias/gold/
└── daily_users_metric/
    ├── platform=HackerNews/
    │   ├── date=2026-01-15/
    │   │   └── data_001.parquet
    │   └── date=2026-01-16/
    │       └── data_001.parquet
    └── platform=X/
        ├── date=2026-01-15/
        │   └── data_001.parquet
        └── date=2026-01-16/
            └── data_001.parquet
```

**Partitioning:** by `platform` and `date`

---

### 4. Data visualization (8 pts)

Visualize gold-layer metrics and KPIs using **Apache Superset**.

Because Superset does **not** read Parquet directly from S3:
1. Store metrics/KPIs in **PostgreSQL**
2. Configure Superset to read from PostgreSQL
3. Host **PostgreSQL and Apache Superset on EC2**
4. Implement a **Lambda function** that moves metrics/KPIs from S3 (gold) to PostgreSQL on EC2

Reference: https://superset.apache.org/

---

### 5. Notifications (5 pts)

Send notifications when any job **fails or does not complete successfully**.

**Discord** via webhook.

- Bronze Lambdas read webhook URL from SSM (`DISCORD_WEBHOOK_PARAMETER_NAME`); enabled when parameter is set
- Notify on failure of: HN ingestion, X dataset ingestion, silver normalization, gold transformation, S3→PostgreSQL load, and any Step Functions / scheduled jobs
- Never commit webhook URLs or other secrets to the repo

---

## Non-Functional Requirements

### 6. Infrastructure as Code (elimination criterion)

All infrastructure is defined in **CloudFormation** under `infra/cloudformation/`:

| Stack | Template | Contents |
|-------|----------|----------|
| network | `network.yaml` | VPC, subnets, IGW, optional NAT, S3 VPC endpoint, Lambda security group |
| storage | `storage.yaml` | Data lake bucket, artifact bucket |
| bronze | `bronze.yaml` | Bronze Lambdas, IAM, EventBridge Scheduler + S3 event rule |
| github-oidc | `github-oidc.yaml` | GitHub Actions deploy role (one-time bootstrap) |

Deploy via GitHub Actions (`.github/workflows/deploy.yml`) or AWS CLI. Lambda code is packaged with `scripts/package_lambdas.sh`.

**Projects that do not meet the IaC requirement will not be reviewed.**

### 7. Network security (3 pts)

- VPC provisioned in `network.yaml` (`10.42.0.0/16`)
- Apply **least privilege**
- Allow only **minimally required** network communication between services
- Use **security groups** and network rules
- Attach compute (Lambda, EC2) to VPC as layers are added

---

## Grading

| # | Requirement | Points |
|---|-------------|--------|
| 1 | Data collection (bronze layer) | 10 |
| 2 | Data normalization (silver layer) | 14 |
| 3 | Data transformation (gold layer) | 10 |
| 4 | Data visualization | 8 |
| 5 | Notifications | 5 |
| 6 | Network security control | 3 |
| | **Total** | **50** |

IaC is not separately scored but is **mandatory** (elimination if missing).

---

## Exam Rules

- Teams of **up to 3 members**
- Any programming language and framework allowed; limited instructor support for technologies not covered in labs
- Cases not covered in this spec may be resolved as the team sees fit
- Submission via a **mid-semester checkpoint** and a **defense** during exam periods:
  - once in June–July exam term
  - once in August–September exam term

---

## Agent Implementation Notes

**Bronze (done):**
- `hackernews-bronze-ingest` — scheduled HN API → `bronze/hackernews/.../items.json`
- `x-bronze-ingest` — `incoming/x/` upload → `bronze/x/{dataset}/raw/...`
- CloudFormation stacks: network, storage, bronze; CI in `.github/workflows/deploy.yml`

**Do (remaining work):**
- Implement silver and gold Lambdas; partition Parquet output
- EC2 with PostgreSQL + Superset; S3→PostgreSQL loader Lambda
- Wire **Discord** failure notifications to all pipeline jobs
- Attach Lambda/EC2 to VPC; tighten security groups (least privilege)
- Add new Lambdas under `lambdas/` + `infra/cloudformation/` + `deploy.yml`

**Do not:**
- Transform or normalize data in bronze Lambdas
- Call the X/Twitter API
- Change bronze paths without updating tests and CloudFormation IAM policies
- Assume Superset can query S3 Parquet directly
- Commit Discord webhook URLs or other secrets to git

**Still open (team choice):**
- Exact silver/gold schema beyond the examples
- Step Functions vs. single Lambda per stage
