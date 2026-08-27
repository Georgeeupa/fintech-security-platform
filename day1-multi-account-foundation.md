# Day 1 — Multi-Account AWS Foundation (Governance Layer)

Run these from the **management account** unless otherwise noted. Requires AWS CLI v2, credentials for the management account, and `jq` for parsing output.

---

## 1. Enable AWS Organizations (all features)

```bash
aws organizations create-organization --feature-set ALL
```

If Organizations already exists in "consolidated billing" mode only, upgrade it:

```bash
aws organizations enable-all-features
# Every member account must then approve — check status:
aws organizations describe-organization
```

Capture the org root ID (you'll need it below):

```bash
ROOT_ID=$(aws organizations list-roots --query 'Roots[0].Id' --output text)
echo $ROOT_ID   # e.g. r-abc1
```

---

## 2. Create the OU structure

`Root → Security OU → Production OU → Development OU` (Security, Production, Development are siblings directly under Root — this is the standard AWS Landing Zone pattern; "Security OU" is not a parent of the other two).

```bash
SEC_OU=$(aws organizations create-organizational-unit \
  --parent-id $ROOT_ID --name "Security" \
  --query 'OrganizationalUnit.Id' --output text)

PROD_OU=$(aws organizations create-organizational-unit \
  --parent-id $ROOT_ID --name "Production" \
  --query 'OrganizationalUnit.Id' --output text)

DEV_OU=$(aws organizations create-organizational-unit \
  --parent-id $ROOT_ID --name "Development" \
  --query 'OrganizationalUnit.Id' --output text)

echo "Security=$SEC_OU  Production=$PROD_OU  Development=$DEV_OU"
```

### Create or invite member accounts

New account (repeat per account — logging, audit, prod workload, dev):

```bash
aws organizations create-account \
  --email "aws-logging@yourcompany.com" \
  --account-name "Logging"

# Poll until status = SUCCEEDED, then grab the account ID
aws organizations list-accounts-for-parent --parent-id $ROOT_ID
```

Move each account into its OU:

```bash
aws organizations move-account \
  --account-id <LOGGING_ACCOUNT_ID> \
  --source-parent-id $ROOT_ID \
  --destination-parent-id $SEC_OU

aws organizations move-account \
  --account-id <PROD_ACCOUNT_ID> \
  --source-parent-id $ROOT_ID \
  --destination-parent-id $PROD_OU

aws organizations move-account \
  --account-id <DEV_ACCOUNT_ID> \
  --source-parent-id $ROOT_ID \
  --destination-parent-id $DEV_OU
```

**Deliverable — org structure diagram:** the diagram above (Root → Security/Production/Development OUs → member accounts) plus:

```bash
aws organizations list-organizational-units-for-parent --parent-id $ROOT_ID
aws organizations list-accounts-for-parent --parent-id $PROD_OU
```
Screenshot the AWS Organizations console tree view for the auditor deliverable — it renders this same hierarchy automatically.

---

## 3. SCP: block `ec2:TerminateInstances` and `cloudtrail:StopLogging` on Production

First enable SCPs as a policy type on the root (one-time):

```bash
aws organizations enable-policy-type \
  --root-id $ROOT_ID \
  --policy-type SERVICE_CONTROL_POLICY
```

### SCP JSON — `scp-prod-guardrails.json`

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "DenyEC2Termination",
      "Effect": "Deny",
      "Action": "ec2:TerminateInstances",
      "Resource": "*"
    },
    {
      "Sid": "DenyCloudTrailStop",
      "Effect": "Deny",
      "Action": [
        "cloudtrail:StopLogging",
        "cloudtrail:DeleteTrail",
        "cloudtrail:UpdateTrail"
      ],
      "Resource": "*"
    }
  ]
}
```

> Including `DeleteTrail`/`UpdateTrail` closes the obvious bypass (an attacker with `iam:*` in the account can't just delete or reconfigure the trail instead of stopping it). Drop those two lines if the exam/rubric wants the SCP scoped to the literal two actions only.

### Create and attach

```bash
POLICY_ID=$(aws organizations create-policy \
  --name "Prod-Guardrails" \
  --description "Deny EC2 termination and CloudTrail tampering in Production" \
  --type SERVICE_CONTROL_POLICY \
  --content file://scp-prod-guardrails.json \
  --query 'Policy.PolicySummary.Id' --output text)

aws organizations attach-policy \
  --policy-id $POLICY_ID \
  --target-id $PROD_OU
```

Verify attachment:

```bash
aws organizations list-policies-for-target \
  --target-id $PROD_OU \
  --filter SERVICE_CONTROL_POLICY
```

---

## 4. Prove the SCP overrides local IAM (this is the "denied action" screenshot)

Inside the **production member account**, create an IAM user/role that is explicitly allowed to terminate instances:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    { "Effect": "Allow", "Action": "ec2:*", "Resource": "*" }
  ]
}
```

Attach that permissive policy to a test role, assume it, then attempt the denied action:

```bash
aws sts assume-role \
  --role-arn arn:aws:iam::<PROD_ACCOUNT_ID>:role/TestFullEC2Access \
  --role-session-name scp-test

# Using those temp creds:
aws ec2 terminate-instances --instance-ids i-0123456789abcdef0
```

Expected result — the call fails even though IAM says Allow:

```
An error occurred (AccessDenied) when calling the TerminateInstances operation:
User: arn:aws:sts::<PROD_ACCOUNT_ID>:assumed-role/TestFullEC2Access/scp-test
is not authorized to perform: ec2:TerminateInstances on resource: arn:aws:ec2:...
with an explicit deny in a service control policy
```

You can also prove it without touching a real instance, using the IAM policy simulator (evaluates SCP + IAM together only via the actual API call — the simulator itself only evaluates identity-based/resource policies, so the CLI error above is the real evidence; use this simulator call just to confirm the local IAM side is Allow):

```bash
aws iam simulate-principal-policy \
  --policy-source-arn arn:aws:iam::<PROD_ACCOUNT_ID>:role/TestFullEC2Access \
  --action-names ec2:TerminateInstances \
  --resource-arns arn:aws:ec2:us-east-1:<PROD_ACCOUNT_ID>:instance/i-0123456789abcdef0
```

**Deliverable:** screenshot of the `AccessDenied ... explicit deny in a service control policy` CLI/console error — this is the proof the exam/rubric wants, since it shows the deny came from the SCP layer, not IAM.

---

## 5. Organization-wide CloudTrail → centralized logging account

Run this from the **management account**. It creates one trail that captures every account in the org and writes to a bucket in the Logging account.

### 5a. In the Logging account: create the destination bucket + policy

```bash
aws s3api create-bucket \
  --bucket org-cloudtrail-logs-<UNIQUE_SUFFIX> \
  --region us-east-1
```

`cloudtrail-bucket-policy.json` (run in Logging account, replace `ORG_ID` and bucket name):

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AWSCloudTrailAclCheck",
      "Effect": "Allow",
      "Principal": { "Service": "cloudtrail.amazonaws.com" },
      "Action": "s3:GetBucketAcl",
      "Resource": "arn:aws:s3:::org-cloudtrail-logs-<UNIQUE_SUFFIX>"
    },
    {
      "Sid": "AWSCloudTrailWrite",
      "Effect": "Allow",
      "Principal": { "Service": "cloudtrail.amazonaws.com" },
      "Action": "s3:PutObject",
      "Resource": "arn:aws:s3:::org-cloudtrail-logs-<UNIQUE_SUFFIX>/AWSLogs/*",
      "Condition": {
        "StringEquals": {
          "s3:x-amz-acl": "bucket-owner-full-control",
          "aws:PrincipalOrgID": "<ORG_ID>"
        }
      }
    }
  ]
}
```

```bash
aws s3api put-bucket-policy \
  --bucket org-cloudtrail-logs-<UNIQUE_SUFFIX> \
  --policy file://cloudtrail-bucket-policy.json
```

Get your Org ID for the condition above:

```bash
aws organizations describe-organization --query 'Organization.Id' --output text
```

### 5b. In the management account: create the org trail

```bash
aws cloudtrail create-trail \
  --name org-trail \
  --s3-bucket-name org-cloudtrail-logs-<UNIQUE_SUFFIX> \
  --is-organization-trail \
  --is-multi-region-trail \
  --enable-log-file-validation

aws cloudtrail start-logging --name org-trail
```

`--is-organization-trail` is what makes this apply to every current and future account in the org automatically — member accounts can't disable or delete it locally (and the SCP above blocks `StopLogging`/`DeleteTrail`/`UpdateTrail` as a second layer of defense specifically in Production).

### Verify centralization

```bash
aws cloudtrail get-trail-status --name org-trail
aws cloudtrail describe-trails --trail-name-list org-trail

# From the logging account, confirm objects are landing from multiple account IDs:
aws s3 ls s3://org-cloudtrail-logs-<UNIQUE_SUFFIX>/AWSLogs/ --recursive | head -20
```

You should see prefixes like `AWSLogs/<PROD_ACCOUNT_ID>/...` and `AWSLogs/<DEV_ACCOUNT_ID>/...` all inside the one bucket owned by the Logging account.

**Deliverable:** `describe-trails` output showing `IsOrganizationTrail: true`, plus the S3 listing showing log prefixes from more than one account ID landing in the centralized bucket.

---

## Recap of deliverables produced in this section

| Requirement | Evidence |
|---|---|
| Org structure diagram | Console tree screenshot / `list-organizational-units-for-parent` + `list-accounts-for-parent` output |
| SCP JSON | `scp-prod-guardrails.json` above |
| Screenshot of denied action | CLI `AccessDenied ... explicit deny in a service control policy` error |
| CloudTrail centralized | `describe-trails` (`IsOrganizationTrail: true`) + S3 listing with multiple account prefixes |

Next up (Day 2) is the permission boundary + `DevOpsEngineer` role and the GitHub OIDC federation — say the word when you want to move on.
