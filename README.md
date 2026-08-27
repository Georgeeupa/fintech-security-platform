# Enterprise-Grade Multi-Account Security Platform on AWS

## Presentation Guide

**Project:** Fully Automated, Multi-Account, Zero-Trust Security Platform  
**Prepared by:** George Eupa  
**Primary AWS Region:** `us-east-2` (Ohio)  
**Industry scenario:** Nairobi-based fintech regulated by the Central Bank of Kenya  

---

## 1. Executive Summary

This project demonstrates a secure, multi-account AWS cloud foundation for mission-critical financial workloads. The architecture combines centralized governance, zero-trust identity, continuous compliance, automated incident response, application-layer protection, and full-stack encryption.

The solution was implemented and validated using the **AWS Management Console**. The presentation focuses on the deployed controls, architectural decisions, automated workflows, test evidence, and business value rather than command-line implementation.

### Key outcomes

- Production guardrails enforced through AWS Organizations and Service Control Policies.
- Temporary, federated CI/CD access implemented through GitHub OpenID Connect.
- Destructive S3 operations restricted through an IAM permission boundary.
- High-severity GuardDuty findings automatically processed through EventBridge, Step Functions, and Lambda.
- Security evidence stored centrally in Amazon S3 and alerts delivered through Amazon SNS.
- AWS Config continuously evaluates resource compliance.
- Security Hub centralizes findings from GuardDuty, Config, and Inspector.
- AWS WAF protects the application from common web attacks and excessive request rates.
- Customer-managed AWS KMS keys protect critical data at rest.
- AWS Certificate Manager provides trusted TLS certificates for HTTPS traffic.

---

## 2. Business Problem

The organization is migrating regulated financial services from local data centers to AWS. The cloud platform must protect sensitive workloads while allowing development and operations teams to deploy applications efficiently.

The principal risks addressed by the project are:

- Unauthorized termination of production resources.
- Disabling or tampering with audit logging.
- Long-lived CI/CD credentials being exposed.
- Excessive IAM permissions.
- Unencrypted data or security logs.
- Undetected malicious network behavior.
- Slow and inconsistent manual incident response.
- Misconfigured S3 buckets and other compliance drift.
- SQL injection, cross-site scripting, and application request floods.
- Findings being fragmented across multiple AWS services and accounts.

---

## 3. Target Architecture

```text
                         AWS ORGANIZATIONS
                                |
              +-----------------+-----------------+
              |                 |                 |
              v                 v                 v
         Security OU       Production OU     Development OU
              |                 |                 |
       Security tooling     ALB and WAF        CI/CD testing
       Central findings     EC2 or ECS          Development
       Incident response    Encrypted S3        workloads
       Logging account      KMS and ACM
              |
              v
       Central monitoring
       and audit evidence
```

### Core security flows

```text
Governance:
AWS Organizations -> Production OU -> Service Control Policy

CI/CD identity:
GitHub Actions -> GitHub OIDC -> AWS STS -> Deployment Role

Incident response:
GuardDuty -> EventBridge -> Step Functions -> Lambda
                                      |          |
                                      |          +-> EC2 isolation
                                      |          +-> S3 evidence
                                      |          +-> SNS alert

Compliance:
AWS Config -> Managed Rule -> Auto-Remediation -> Reevaluation

Finding aggregation:
GuardDuty + AWS Config + Inspector -> Security Hub -> EventBridge -> SNS

Application protection:
Internet -> AWS WAF -> HTTPS ALB -> EC2 or ECS application

Encryption:
AWS KMS -> S3, logs, secrets, and incident evidence
AWS ACM -> HTTPS listener on Application Load Balancer
```

---

## 4. Multi-Account Governance

The platform uses AWS Organizations with all features enabled. Security, Production, and Development are separated into organizational units so that policies can be applied according to workload purpose and risk.

### Organizational structure

- **Management account:** Organization-level governance and policy administration.
- **Security OU:** Central security tooling, monitoring, and audit functions.
- **Production OU:** Mission-critical application resources and protected production data.
- **Development OU:** Non-production development and testing workloads.
- **Logging account:** Central destination for organization-wide audit logs.

### Production Service Control Policy

The Production OU has a Service Control Policy that denies:

- `ec2:TerminateInstances`
- `cloudtrail:StopLogging`

The guardrail applies even when a user or role has a local IAM policy such as AdministratorAccess. This demonstrates that an explicit organization-level deny overrides a local IAM allow.

### Console presentation

Open the following pages during the demonstration:

1. **AWS Organizations > AWS accounts**
   - Show the organizational units and member accounts.
2. **AWS Organizations > Policies > Service control policies**
   - Open `ProductionSecuritySCP`.
3. **Production OU > Policies**
   - Show that the policy is attached to the Production OU.
4. Show evidence of a denied production action.

### Design decision

SCPs provide scalable preventive governance across accounts. They do not grant permissions. They define the maximum permissions available to accounts under the policy attachment point.

### Trade-off

A broad production deny reduces accidental or malicious destruction but may also block legitimate emergency recovery. A real enterprise platform should include a separately governed, monitored, and time-limited break-glass process.

---

## 5. Centralized Audit Logging

An organization-wide CloudTrail records supported management activity from the management and member accounts. Logs are delivered to a centralized S3 bucket to separate audit evidence from workload administration.

### Security controls

- Organization trail enabled.
- Multi-Region trail enabled.
- Central S3 log destination.
- S3 versioning enabled.
- Public access blocked.
- KMS encryption applied where configured.
- Production SCP prevents users from stopping CloudTrail logging.

### Console presentation

1. Open **CloudTrail > Trails**.
2. Select the organization trail.
3. Show:
   - Logging status.
   - Organization trail status.
   - Multi-Region status.
   - S3 destination.
   - KMS encryption configuration.
4. Open the central logging bucket in Amazon S3.
5. Show account and organization log prefixes.

### Evidence expected

- Trail status is logging.
- The trail is marked as an organization trail.
- Log files from more than one account are visible in the central bucket.

---

## 6. IAM Governance and Zero-Trust Access

### Permission boundary

The `FintechDevOpsBoundary` defines the maximum permissions available to the `DevOpsEngineer` role. The role can be granted S3 permissions, but the boundary prevents destructive operations such as deleting buckets or objects.

### Console presentation

1. Open **IAM > Policies > FintechDevOpsBoundary**.
2. Show the denied destructive S3 actions.
3. Open **IAM > Roles > DevOpsEngineer**.
4. Show:
   - Attached permission policies.
   - Attached permissions boundary.
5. Present evidence that an allowed S3 operation succeeded and a destructive operation was denied.

### GitHub OIDC federation

GitHub Actions authenticates to AWS using OpenID Connect instead of stored AWS access keys. AWS validates the GitHub token and issues short-lived credentials through AWS STS.

The trust relationship is restricted to:

- **Repository owner:** `georgeeupa`
- **Repository:** `fintech-security-platform`
- **Branch:** `main`
- **Audience:** `sts.amazonaws.com`

### Console presentation

1. Open **IAM > Identity providers**.
2. Select `token.actions.githubusercontent.com`.
3. Show the OIDC provider URL and audience.
4. Open **IAM > Roles > GitHubDeploymentRole**.
5. Open the **Trust relationships** tab.
6. Show the repository and branch restrictions.
7. In GitHub, open the successful Actions workflow.
8. Show the identity returned during the workflow, which should contain `assumed-role/GitHubDeploymentRole`.

### Negative test

Run the workflow from an unauthorized repository or branch. AWS STS should reject the role assumption because the OIDC subject claim does not match the role trust policy.

### Design decision

OIDC eliminates long-lived AWS credentials from GitHub. Each run receives temporary, auditable credentials with a limited lifetime.

### Trade-off

OIDC shifts part of the trust boundary to GitHub repository governance. Branch protection, code review, minimal workflow permissions, protected environments, and careful control of third-party actions are required.

---

## 7. Automated Incident Response

The incident-response workflow automatically handles high-severity GuardDuty findings.

```text
GuardDuty
    |
    v
EventBridge rule
    |
    v
Step Functions workflow
    |
    v
Incident-response Lambda
    |
    +----> Store evidence in S3
    +----> Notify security team through SNS
    +----> Isolate or tag affected EC2 instance
```

### GuardDuty

GuardDuty continuously analyzes supported AWS data sources for suspicious behavior. The project uses high-severity findings as the trigger for automated response.

### EventBridge

The `Fintech-GuardDuty-HighSeverity` rule filters GuardDuty events and targets the Step Functions state machine.

### Step Functions

`FintechIncidentResponseWorkflow` coordinates incident handling. The state machine provides:

- Repeatable execution.
- Retries for temporary service failures.
- Execution history.
- Consistent input handling.
- Clear success and failure states.

### Lambda

`FintechIncidentResponse` performs controlled response actions:

- Validates finding information.
- Records the finding in an incident evidence bucket.
- Sends an SNS notification.
- Tags or isolates the affected EC2 instance.
- Writes execution logs to CloudWatch Logs.

### Console presentation

1. Open **GuardDuty > Findings** and show a high-severity sample finding.
2. Open **EventBridge > Rules > Fintech-GuardDuty-HighSeverity**.
3. Show:
   - Rule is enabled.
   - Event pattern filters GuardDuty findings.
   - Target is the Step Functions state machine.
4. Open **Step Functions > FintechIncidentResponseWorkflow**.
5. Show a successful execution and its graph view.
6. Open the execution details and show the original finding input.
7. Open **Lambda > FintechIncidentResponse > Monitor**.
8. Open the corresponding CloudWatch log stream.
9. Open the incident S3 bucket and show the evidence object.
10. Open the SNS topic and show its confirmed subscription.
11. Show the notification received by the security team.
12. Open the EC2 instance and show the isolation tag or security-group change.

### Design decision

Step Functions is used instead of connecting EventBridge directly to Lambda because orchestration makes remediation consistent, observable, retryable, and easier to extend.

### Trade-off

Automatic EC2 isolation dramatically reduces containment time but can interrupt legitimate production services. Production implementation should validate confidence, preserve previous security groups, support rollback, and use approval for lower-confidence findings.

---

## 8. Continuous Compliance

AWS Config continuously records supported resource configurations and evaluates them against compliance rules.

### Implemented rule

- `s3-bucket-server-side-encryption-enabled`

The rule checks whether S3 buckets have a server-side encryption configuration.

### Auto-remediation flow

```text
Non-compliant bucket created
          |
          v
AWS Config detects configuration
          |
          v
Rule reports NON_COMPLIANT
          |
          v
Remediation applies encryption
          |
          v
AWS Config reevaluates resource
          |
          v
Rule reports COMPLIANT
```

### Console presentation

1. Open **AWS Config > Settings**.
2. Show that the configuration recorder is enabled.
3. Open **AWS Config > Rules**.
4. Select `s3-bucket-server-side-encryption-enabled`.
5. Show:
   - Active rule.
   - Resource compliance results.
   - Remediation configuration.
6. Show the test bucket when non-compliant.
7. Show the remediation execution.
8. Open the test bucket and confirm that encryption was applied.
9. Return to AWS Config and show the compliant reevaluation.

### Design decision

Continuous compliance closes the gap between deployment and periodic audits. Auto-remediation shortens the time a resource remains misconfigured and applies the approved control consistently.

### Trade-off

Automatic remediation must be tightly scoped and idempotent. An incorrect remediation can make resources unavailable or apply the wrong encryption key. High-impact controls may require approval or staged rollout.

---

## 9. Centralized Security Monitoring

AWS Security Hub provides the central findings view for security and compliance information.

### Integrated services

- Amazon GuardDuty.
- AWS Config.
- Amazon Inspector.
- AWS Foundational Security Best Practices.

### Inspector coverage

Inspector continuously assesses supported resources, including:

- Amazon EC2 instances.
- Amazon ECR container images.
- AWS Lambda functions.

### Console presentation

1. Open **Security Hub > Summary**.
2. Show the enabled security standard.
3. Open **Security Hub > Findings**.
4. Filter findings by product name:
   - GuardDuty.
   - Config.
   - Inspector.
5. Show severity distribution and selected finding details.
6. Open **Amazon Inspector > Account management or Coverage**.
7. Show enabled resource types and assessment coverage.
8. Open the EventBridge rule used for high-severity Security Hub alerts.
9. Show the SNS target and a delivered test alert.

### Full-marks evidence

- Findings from multiple services visible in Security Hub.
- High-severity alert rule enabled.
- SNS subscription confirmed.
- Alert delivery demonstrated.
- Security Hub findings include account, region, resource, severity, and remediation information.

---

## 10. Application and Edge Security

The sample web application is deployed behind an internet-facing Application Load Balancer. The application target should accept traffic only from the ALB security group.

### Request path

```text
User
  |
  v
AWS WAF Web ACL
  |
  v
ALB HTTPS listener on port 443
  |
  v
Target group
  |
  v
EC2 or ECS application
```

### WAF rules

The regional `FintechWebACL` includes:

1. **AWSManagedRulesCommonRuleSet**
   - Provides protections for common application-layer threats and malformed requests.
2. **RateLimit100**
   - Aggregates requests by source IP.
   - Blocks traffic exceeding the configured request threshold.

### Console presentation

1. Open **AWS WAF & Shield > Web ACLs > FintechWebACL**.
2. Show:
   - Regional scope.
   - Default action.
   - Managed rule group.
   - Rate-based rule.
3. Open **Associated AWS resources**.
4. Show the protected Application Load Balancer.
5. Open **Logging and metrics**.
6. Show that WAF logging is enabled.
7. Open **Sampled requests**.
8. Show blocked SQL injection, cross-site scripting, or rate-limit test requests.
9. Open CloudWatch metrics and show allowed and blocked request counts.

### Attack tests

#### SQL injection test

Expected result:

- Request blocked with HTTP 403, or recorded as a terminating managed-rule match.
- WAF sampled request identifies the responsible rule.

#### Cross-site scripting test

Expected result:

- Request blocked by the applicable managed-rule component.
- WAF logs contain the request action and terminating rule.

#### Rate-limit test

Expected result:

- Initial requests are allowed.
- Subsequent requests from the same source are blocked after the threshold is exceeded.
- WAF metrics show blocked requests.

### ALB versus CloudFront decision

WAF is associated with the ALB because the demonstrated application is regional and the assessment explicitly requires ALB protection. CloudFront would be preferred for a geographically distributed public application requiring edge caching, origin shielding, and attack blocking closer to users.

---

## 11. Full-Stack Encryption

### Customer-managed KMS key

A customer-managed symmetric KMS key protects sensitive data. Automatic key rotation is enabled.

### Critical data paths

| Data path | Protection | Console evidence |
|---|---|---|
| Application S3 objects | SSE-KMS | Bucket default encryption and object properties |
| Incident evidence | SSE-KMS | Incident bucket encryption and object KMS key |
| CloudTrail logs | KMS encryption | Trail configuration and KMS key reference |
| CloudWatch log groups | KMS encryption where configured | Log group details |
| Application secrets | Secrets Manager or encrypted Parameter Store | Secret encryption key and restricted access |
| Internet traffic | TLS through ACM | HTTPS listener and issued certificate |

### Console presentation

#### KMS

1. Open **KMS > Customer managed keys**.
2. Select the fintech security key.
3. Show:
   - Key state is enabled.
   - Key type is symmetric.
   - Automatic rotation is enabled.
   - Key policy and authorized services.

#### S3

1. Open the protected S3 bucket.
2. Open **Properties > Default encryption**.
3. Show SSE-KMS and the expected customer-managed key.
4. Open a test object.
5. Show that the object is encrypted with AWS KMS.

#### CloudTrail and logs

1. Open the organization trail.
2. Show the configured KMS key.
3. Open sensitive CloudWatch log groups.
4. Show the associated KMS key where enabled.

### Design decision

Customer-managed KMS keys provide stronger control over key policy, rotation, separation of duties, auditing, and revocation than service-managed encryption alone.

### Trade-off

Customer-managed keys introduce cost and policy complexity. An incorrect key policy can prevent CloudTrail, S3, or an application from using the key. Key policies and resource policies must therefore be tested together.

---

## 12. TLS and AWS Certificate Manager

AWS Certificate Manager provides the public certificate used by the Application Load Balancer.

### Listener configuration

- Port 80 receives HTTP traffic and redirects it to HTTPS.
- Port 443 terminates TLS using the ACM certificate.
- The HTTPS listener forwards valid traffic to the application target group.

### Console presentation

1. Open **Certificate Manager > Certificates**.
2. Show:
   - Certificate status is `Issued`.
   - Domain name matches the application hostname.
   - Certificate is in the same Region as the ALB.
3. Open **EC2 > Load Balancers > fintech-alb > Listeners and rules**.
4. Show:
   - HTTP listener on port 80.
   - HTTP-to-HTTPS redirect action.
   - HTTPS listener on port 443.
   - Attached ACM certificate.
5. Open the application in a browser.
6. Show the secure connection and certificate details.

---

## 13. Automation Completeness

Automation is considered complete only when the workflow is configured, automatically triggered, successfully executed, and supported by evidence.

### Automated processes

- GitHub push automatically starts the deployment workflow.
- GitHub OIDC automatically obtains temporary AWS credentials.
- GuardDuty findings automatically trigger EventBridge.
- EventBridge automatically starts Step Functions.
- Step Functions automatically invokes Lambda.
- Lambda automatically stores evidence, notifies SNS, and performs isolation.
- AWS Config automatically evaluates S3 encryption compliance.
- Config remediation automatically corrects a non-compliant bucket.
- Security Hub automatically aggregates findings.
- Inspector continuously evaluates supported workloads.
- WAF automatically blocks matching malicious requests.

### Reproducibility

The resource configuration is documented by deployment phase:

1. Governance and centralized logging.
2. IAM governance and GitHub federation.
3. Detection and incident response.
4. Compliance and findings aggregation.
5. Application, ALB, HTTPS, and WAF.
6. Encryption across critical data paths.
7. Validation and evidence collection.

The presentation demonstrates the implemented resources through the AWS Console. Infrastructure definitions, policies, workflow files, and application artifacts should remain in source control so that the platform can be recreated consistently.

---

## 14. End-to-End Validation Scenarios

### Scenario 1: Misconfigured S3 bucket

**Action:** Create a test bucket without the required encryption configuration.

**Expected automation:**

1. AWS Config identifies the bucket.
2. The encryption rule reports non-compliance.
3. Auto-remediation applies encryption.
4. Config reevaluates the bucket as compliant.
5. The related security finding updates in Security Hub.

**Presentation evidence:**

- Config rule status before remediation.
- Remediation execution.
- Bucket encryption after remediation.
- Config rule status after reevaluation.

### Scenario 2: Malicious network activity

**Action:** Generate an approved GuardDuty sample finding.

**Expected automation:**

1. GuardDuty creates a high-severity finding.
2. EventBridge matches the finding.
3. Step Functions starts automatically.
4. Lambda processes the event.
5. Evidence is written to S3.
6. The security team receives an SNS alert.
7. The affected test instance is tagged or isolated.

**Presentation evidence:**

- GuardDuty finding.
- EventBridge rule and state-machine target.
- Successful Step Functions execution.
- Lambda CloudWatch logs.
- S3 evidence object.
- SNS alert.
- EC2 isolation state.

### Scenario 3: Unauthorized CI/CD attempt

**Action:** Start the workflow from a repository or branch that is not authorized by the trust policy.

**Expected automation:**

- AWS STS denies role assumption.
- No deployment action occurs.
- The failed authentication is auditable.

**Presentation evidence:**

- Failed GitHub Actions job.
- OIDC trust policy restriction.
- No static AWS secrets configured in GitHub.

### Scenario 4: Application attack

**Action:** Perform controlled SQL injection, cross-site scripting, and request-rate tests against the sample application.

**Expected automation:**

- WAF evaluates every request.
- Managed rules block matching attack patterns.
- The rate-based rule blocks traffic exceeding the threshold.
- Logs and metrics record the events.

**Presentation evidence:**

- HTTP 403 test output.
- WAF sampled requests.
- WAF log events.
- CloudWatch blocked-request metrics.

---

## 15. Threat and Control Mapping

| Threat | Preventive controls | Detective and response controls |
|---|---|---|
| Production resource destruction | SCP explicit deny, least privilege, separation of duties | CloudTrail and Security Hub |
| CI/CD credential exposure | GitHub OIDC, STS temporary credentials, restricted role trust | CloudTrail assumed-role events |
| Excessive IAM permissions | Permissions boundary and scoped role policies | IAM review and CloudTrail |
| Compromised EC2 instance | Security groups, private placement, encrypted secrets | GuardDuty, Inspector, automated isolation |
| Unencrypted S3 storage | Default encryption, KMS key, policy controls | Config rule and auto-remediation |
| Audit-log tampering | Central logging, SCP, KMS, bucket restrictions | CloudTrail delivery monitoring |
| SQL injection or XSS | AWS WAF managed rules | WAF logs, sampled requests, metrics |
| HTTP request flood | WAF rate-based rule | Blocked-request metrics and logs |
| Vulnerable software | Patch management and controlled images | Inspector continuous scanning |

---

## 16. Exam-Style Architecture Justifications

### SCPs and permission boundaries

An SCP limits the maximum permissions available in accounts governed through AWS Organizations. It does not grant access. A permissions boundary limits the maximum permissions that an IAM user or role can receive from identity policies. SCPs provide organization-wide guardrails, while boundaries support safe permission delegation inside an account.

### Why OIDC is preferred

OIDC avoids storing long-lived AWS access keys. GitHub presents a signed identity token, AWS validates the token claims, and STS issues temporary credentials. Repository and branch restrictions reduce unauthorized use, while CloudTrail records the resulting role session.

### Why Step Functions is used

Step Functions provides a defined, observable incident workflow with retries, failure handling, ordered tasks, execution history, and consistent input processing. This creates repeatable remediation and makes response evidence easier to audit.

### WAF on ALB versus CloudFront

ALB association is suitable for this regional application and provides direct protection for the deployed load balancer. CloudFront association would provide edge-based protection and caching for a global application, but would add distribution configuration, caching decisions, and additional operational complexity.

### Why auto-remediation is critical

Detection alone leaves a period during which a resource remains non-compliant. Auto-remediation reduces that exposure window, enforces approved configuration consistently, and produces repeatable compliance evidence. Remediation must remain scoped, observable, idempotent, and reversible.

---

## 17. Presentation Sequence

Use the following order for a concise live demonstration:

1. **Architecture overview**
   - Explain the accounts, OUs, trust boundaries, and security flows.
2. **AWS Organizations**
   - Show OU structure and Production SCP attachment.
3. **CloudTrail**
   - Show active organization trail and centralized S3 logs.
4. **IAM governance**
   - Show permission boundary, DevOpsEngineer, OIDC provider, and GitHub role trust.
5. **GitHub Actions**
   - Show a successful temporary-credential deployment and failed unauthorized attempt.
6. **GuardDuty**
   - Show the sample high-severity finding.
7. **EventBridge and Step Functions**
   - Show the event rule, target, and successful execution.
8. **Lambda, SNS, S3, and EC2**
   - Show logs, alert, evidence, and isolation result.
9. **AWS Config**
   - Show recorder status, managed rule, remediation, and compliant result.
10. **Security Hub and Inspector**
    - Show centralized findings and coverage.
11. **ALB, ACM, and HTTPS**
    - Show listeners, redirect, certificate, and target health.
12. **AWS WAF**
    - Show rules, ALB association, sampled blocked requests, logs, and metrics.
13. **KMS and encryption**
    - Show key rotation and encryption across critical paths.
14. **Close with business value**
    - Explain reduced risk, faster response, auditable compliance, and scalable governance.

---

## 18. Evidence Checklist

### Governance

- [ ] AWS Organizations hierarchy.
- [ ] Production SCP JSON.
- [ ] SCP attached to Production OU.
- [ ] Denied EC2 termination or CloudTrail stop action.
- [ ] Active organization CloudTrail.
- [ ] Centralized log objects from member accounts.

### IAM

- [ ] Permission boundary policy.
- [ ] Boundary attached to DevOpsEngineer.
- [ ] Destructive S3 action denied.
- [ ] GitHub OIDC provider.
- [ ] Repository- and branch-restricted trust policy.
- [ ] Successful assumed-role GitHub workflow.
- [ ] Unauthorized workflow attempt denied.

### Incident response

- [ ] GuardDuty high-severity finding.
- [ ] Enabled EventBridge rule.
- [ ] Step Functions target.
- [ ] Successful state-machine execution.
- [ ] Lambda log stream.
- [ ] S3 finding evidence.
- [ ] Delivered SNS notification.
- [ ] EC2 isolation evidence.

### Compliance and monitoring

- [ ] Config recorder enabled.
- [ ] S3 encryption rule active.
- [ ] Non-compliant test state.
- [ ] Remediation execution.
- [ ] Compliant state after remediation.
- [ ] Security Hub standard enabled.
- [ ] Centralized findings from integrated services.
- [ ] Inspector coverage and findings.
- [ ] High-severity SNS alert test.

### Application security and encryption

- [ ] Healthy ALB target group.
- [ ] HTTP-to-HTTPS redirect.
- [ ] ACM certificate status is Issued.
- [ ] WAF associated with ALB.
- [ ] Managed common rules enabled.
- [ ] Rate-based rule enabled.
- [ ] WAF logging enabled.
- [ ] SQL injection and XSS blocked-request evidence.
- [ ] Rate-limit blocked-request evidence.
- [ ] Customer-managed KMS key enabled.
- [ ] Automatic KMS rotation enabled.
- [ ] S3 object encrypted with the expected KMS key.
- [ ] Critical logs and secrets encrypted.

---

## 19. Operational Considerations

### Security

- Use least-privilege policies rather than broad managed policies in production.
- Protect GitHub branches and deployment environments.
- Restrict KMS key administrators separately from key users.
- Maintain a monitored break-glass process.
- Protect centralized logging from deletion and public access.

### Reliability

- Make remediation actions idempotent.
- Preserve previous EC2 security groups for rollback.
- Add retries and controlled failure paths to Step Functions.
- Monitor EventBridge failed invocations and Lambda errors.
- Use multiple Availability Zones for the ALB and application tier.

### Cost

- Define retention and lifecycle policies for CloudTrail, WAF, Config, and application logs.
- Review Security Hub, Config, GuardDuty, Inspector, WAF, KMS, NAT Gateway, and ALB costs.
- Disable unnecessary test resources after evidence has been captured.

### Compliance

- Retain timestamped screenshots and exported findings.
- Record the account and Region for every test.
- Redact tokens, sensitive email addresses, and confidential values.
- Document exceptions, remediation ownership, and review frequency.

---

## 20. Conclusion

The project demonstrates an integrated AWS security platform rather than a collection of isolated services. Governance prevents prohibited production actions. Zero-trust identity removes static CI/CD credentials. Continuous compliance detects and corrects configuration drift. GuardDuty findings trigger an observable incident workflow. Security Hub provides centralized security visibility. WAF protects the application layer, while KMS and ACM protect data at rest and in transit.

The resulting architecture improves the organization's ability to prevent incidents, detect threats, contain compromised resources, prove compliance, and scale cloud operations across multiple AWS accounts.

---

## Presentation Closing Statement

> This platform applies defense in depth across governance, identity, monitoring, incident response, application security, and encryption. Preventive controls restrict unsafe actions, detective controls centralize security findings, and automated remediation reduces response time and configuration drift. The solution uses temporary credentials, organization-level policies, managed security services, and auditable workflows to provide a secure and scalable foundation for regulated fintech workloads on AWS.
