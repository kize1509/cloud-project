# Project Specification — Računarstvo u oblaku

> Source: `Specifikacija projekta.pdf`  
> Audience: agents and developers implementing this project

## Overview

Build an AWS-based platform for **collecting, processing, storing, and analyzing** data from social networks and blog portals.

**Hard requirements:**
- Must run on **AWS**
- Data processing design must follow **Medallion architecture** (bronze → silver → gold)
- All infrastructure must be defined as **Terraform** (IaC) — elimination criterion; projects without IaC will not be reviewed

**Data sources (exactly 2):**
1. **Hacker News** — live ingestion via API (Lambda)
2. **X (Twitter)** — both Kaggle datasets: Bitcoin Tweets + Covid Tweets (see [Project Decisions](#project-decisions))

---

## Project Decisions

These choices are **locked in** for this implementation (originally open in the course spec):

| Area | Decision |
|------|----------|
| **IaC tool** | [Terraform](https://www.hashicorp.com/products/terraform) |
| **Notifications** | [Discord](https://discord.com/) webhook on job failure |
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
Hacker News ──► Lambda ──┐
                         ├──► S3: Sirovi podaci (csv, json, xml)     [bronze]
X (datasets) ──► Lambda ──┘         │
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
| Terraform (IaC — **chosen**) | https://www.hashicorp.com/products/terraform |
| AWS CDK (not used) | https://docs.aws.amazon.com/cdk/v2/guide/home.html |
| CloudFormation (not used) | https://docs.aws.amazon.com/AWSCloudFormation/latest/UserGuide/Welcome.html |
| Terragrunt (not used) | https://terragrunt.gruntwork.io/ |

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
- Use a **Lambda function**
- Write collected data to **S3 in original/raw form**
- **No processing or transformation** allowed at this stage — S3 is the bronze Data Lake layer

**API:** free. Documentation: https://github.com/HackerNews/API  
**Optional helper:** HN Search API (keyword search): https://hn.algolia.com/api

#### 1.2 X (Twitter)

X is a social network for short posts.

**Team decision:** use **both** spec-provided Kaggle datasets — do **not** call the X API.

**Datasets (both required):**
- [Bitcoin Tweets](https://www.kaggle.com/datasets/kaushiksuresh147/bitcoin-tweets)
- [Covid Tweets](https://www.kaggle.com/datasets/gpreda/covid19-tweets)

**Implementation:**
- Load dataset files into the Data Lake bucket in **original/raw form** (bronze layer)
- Use a **Lambda function** (e.g. triggered on S3 upload or on schedule) to copy or ingest the datasets — **no normalization or transformation** at bronze stage
- Preserve source format (csv, json, etc.) as received from the datasets

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

**Team decision:** **Discord** via webhook.

- Notify on failure of: HN ingestion, X dataset ingestion, silver normalization, gold transformation, S3→PostgreSQL load, and any Step Functions / scheduled jobs
- Store webhook URL in Terraform-managed secrets or SSM Parameter Store — never commit it to the repo

---

## Non-Functional Requirements

### 6. Infrastructure as Code (elimination criterion)

All infrastructure must be defined as code. The course spec allows CDK, CloudFormation, Terraform, or Terragrunt.

**Team decision:** **Terraform** — all AWS resources (VPC, S3, Lambda, IAM, EC2, EventBridge, Step Functions, etc.) must live in Terraform modules/config under `infra/` (or equivalent).

**Projects that do not meet the IaC requirement will not be reviewed.**

### 7. Network security (3 pts)

- Entire infrastructure inside a **VPC**
- Apply **least privilege**
- Allow only **minimally required** network communication between services
- Use **security groups** and network rules

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

**Do:**
- Treat bronze/silver/gold as separate S3 prefixes or buckets with clear boundaries
- Keep bronze data immutable and untransformed
- Use Lambda for all processing steps shown in the pipeline diagram
- Partition Parquet output in silver and gold layers
- Wire **Discord** failure notifications to all pipeline jobs (ingestion, normalization, transformation, S3→PostgreSQL load)
- Define VPC, security groups, Lambda, S3, EC2, and orchestration in **Terraform** from day one
- Ingest X data from **both** Kaggle datasets (Bitcoin Tweets + Covid Tweets)

**Do not:**
- Transform or normalize data in the bronze ingestion Lambda
- Call the X/Twitter API
- Skip IaC — project will be rejected
- Assume Superset can query S3 Parquet directly
- Commit Discord webhook URLs or other secrets to git

**Still open (team choice):**
- Exact silver/gold schema beyond the examples
- Step Functions vs. single Lambda per stage
