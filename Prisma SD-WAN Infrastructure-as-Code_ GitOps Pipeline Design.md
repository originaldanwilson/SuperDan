# Prisma SD-WAN Infrastructure-as-Code: GitOps Pipeline Design
## 1. Executive Summary
This document outlines the architecture for managing Palo Alto Prisma SD-WAN ION device configurations as code, using GitHub as the source of truth. Engineers modify YAML configuration files in a `dev` branch, submit pull requests for peer review, and upon approval and merge to `prod`, a GitHub Actions pipeline automatically pushes the validated configuration to the Prisma SD-WAN controller.
## 2. Tooling Options Assessment
### 2.1 Python (prisma_config + prisma_sase SDK) — Recommended Primary Approach
* **prisma_config** (`pip install prisma_config`) is the official Palo Alto CI-capable utility.
* Provides `pull_site` (export YAML from controller) and `do_site` (push YAML to controller).
* Built on the **prisma_sase** Python SDK (current: v6.6.2b1).
* Authentication: OAuth2 service account via `client_id`, `client_secret`, `tsg_id` from Strata Cloud Manager.
* Designed explicitly for the YAML-based workflow you already have working.
* Best practice: one YAML file per site.
* **Verdict: Best fit.** Directly supports your existing `pull_site`/`do_site` workflow and YAML files.
### 2.2 Terraform (prismasdwan provider) — Viable Alternative
* Official provider: `paloaltonetworks/prismasdwan` on the Terraform Registry (current: v6.6.1-beta.2).
* Manages Prisma SD-WAN resources via Strata Cloud Manager (SCM) API.
* Authentication: same OAuth2 service account (`client_id`, `client_secret`, `scope = tsg_id:XXXXX`).
* Provides `terraform plan` for dry-run diffing before apply — strong safety benefit.
* State management tracks drift between desired and actual config.
* **Caveat:** The provider is still in **beta**. You would need to convert your existing YAML configs into HCL `.tf` files. This is a different config format from what `pull_site`/`do_site` produces.
* **Verdict: Good for greenfield or if you want state-managed IaC.** Requires config format migration. Can coexist alongside the Python approach.
### 2.3 Ansible — Possible but Indirect
* No official Ansible collection exists specifically for Prisma SD-WAN ION site configuration management.
* You would wrap the Python SDK or `do_site` CLI calls inside Ansible playbooks using `ansible.builtin.command` or `ansible.builtin.shell` modules, or write custom Ansible modules.
* Ansible provides inventory management, role-based task organization, and idempotency patterns.
* **Verdict: Feasible but adds a layer of abstraction over the Python tools without significant benefit for this use case.** Consider if you already have Ansible in your operational toolchain and want a unified automation framework.
## 3. GitHub Repository Structure
```warp-runnable-command
prisma-sdwan-config/
├── .github/
│   ├── workflows/
│   │   ├── validate-dev.yml          # Runs on PR to dev: lint, schema validation
│   │   ├── deploy-prod.yml           # Runs on merge to prod: push config to controller
│   │   └── drift-check.yml           # Scheduled: detect config drift
│   ├── CODEOWNERS                    # Defines required reviewers
│   └── pull_request_template.md      # Standardized PR template
├── sites/
│   ├── site-chicago.yml              # One YAML per site (best practice)
│   ├── site-boston.yml
│   ├── site-nyc.yml
│   └── site-dallas.yml
├── scripts/
│   ├── validate_yaml.py              # Schema validation script
│   ├── deploy_site.py                # Wrapper around do_site with logging
│   └── pull_all_sites.py             # Utility to refresh YAMLs from controller
├── schemas/
│   └── site-schema.json              # JSON Schema for YAML validation
├── requirements.txt                  # Python dependencies (prisma_config, prisma_sase, pyyaml, jsonschema)
├── README.md                         # Runbook and onboarding documentation
└── CHANGELOG.md                      # Change history
```
If using **Terraform** instead of or alongside Python:
```warp-runnable-command
prisma-sdwan-config/
├── terraform/
│   ├── main.tf                       # Provider config
│   ├── variables.tf                  # Input variables
│   ├── sites/
│   │   ├── chicago.tf
│   │   ├── boston.tf
│   │   └── nyc.tf
│   ├── modules/
│   │   └── site/                     # Reusable site module
│   │       ├── main.tf
│   │       ├── variables.tf
│   │       └── outputs.tf
│   └── backend.tf                    # Remote state (S3, Azure Blob, etc.)
```
## 4. Branch Strategy & Workflow
### 4.1 Branch Model
* **`dev`** — Working branch. Engineers commit YAML changes here.
* **`prod`** — Protected branch. Represents the live/deployed state. Only receives changes via approved PRs from `dev`.
* Optional: **`feature/*`** branches for larger multi-site changes, merged into `dev` first.
### 4.2 Change Workflow (Step-by-Step)
1. Engineer clones repo, creates a working branch or works directly on `dev`.
2. Engineer modifies the YAML file for the target site (e.g., `sites/site-chicago.yml`).
3. Engineer commits and pushes to `dev`.
4. Engineer opens a **Pull Request** from `dev` → `prod`.
5. GitHub Actions triggers **validate-dev.yml** on the PR:
    * YAML syntax check
    * Schema validation against `schemas/site-schema.json`
    * Diff summary posted as a PR comment (what changed)
6. **Peer reviewers** (defined in `CODEOWNERS`) are automatically assigned.
7. Reviewers inspect the diff, validation results, and approve or request changes.
8. Upon **approval + merge to `prod`**, GitHub Actions triggers **deploy-prod.yml**:
    * Identifies which YAML files changed (via `git diff`)
    * Runs `do_site` against only the changed site configs
    * Logs output and posts deployment summary to the PR / Slack
9. Optional: **drift-check.yml** runs on a schedule (e.g., daily) to detect if the controller state has diverged from the repo.
## 5. GitHub Branch Protection Rules (for `prod`)
* Require pull request reviews: **minimum 2 approvals**
* Require status checks to pass: **validate-dev** workflow must succeed
* Require branches to be up to date before merging
* Restrict who can push: only the CI service account / repo admins
* Require conversation resolution before merging
* Optional: require signed commits
## 6. GitHub Actions Pipeline Details
### 6.1 validate-dev.yml (PR Validation)
Trigger: `pull_request` targeting `prod`
Steps:
1. Checkout code
2. Set up Python 3.x
3. `pip install -r requirements.txt`
4. Run `scripts/validate_yaml.py` against changed YAML files
5. Post validation results as a PR comment via `actions/github-script`
### 6.2 deploy-prod.yml (Production Deployment)
Trigger: `push` to `prod` (i.e., after PR merge)
Steps:
1. Checkout code
2. Set up Python 3.x
3. `pip install -r requirements.txt`
4. Identify changed site YAML files via `git diff HEAD~1 --name-only -- sites/`
5. For each changed file, run `do_site <file>` using credentials from GitHub Secrets
6. Capture and log output
7. Post deployment summary (success/failure per site) to PR comment or Slack webhook
8. On failure: open a GitHub Issue automatically
### 6.3 drift-check.yml (Scheduled Drift Detection)
Trigger: `schedule` (cron, e.g., daily at 06:00 UTC)
Steps:
1. Checkout `prod`
2. Run `pull_site -S ALL_SITES --multi-output /tmp/live/`
3. Diff `/tmp/live/*.yml` against `sites/*.yml`
4. If drift detected: open a GitHub Issue with the diff
### 6.4 Terraform Variant (if using Terraform)
* **validate-dev.yml**: `terraform init` → `terraform validate` → `terraform plan` (posted as PR comment)
* **deploy-prod.yml**: `terraform apply -auto-approve` (with remote state locking)
* **drift-check.yml**: `terraform plan -detailed-exitcode` (exit code 2 = drift)
## 7. Secrets Management
Store the following in **GitHub Actions Secrets** (Settings → Secrets and variables → Actions):
* `PRISMA_CLIENT_ID` — Service account client ID
* `PRISMA_CLIENT_SECRET` — Service account client secret
* `PRISMA_TSG_ID` — Tenant Service Group ID
* `SLACK_WEBHOOK_URL` — (Optional) for deployment notifications
These are injected as environment variables in the GitHub Actions runners. The `do_site`/`prisma_sase` SDK reads them at runtime.
## 8. CODEOWNERS File
```warp-runnable-command
# .github/CODEOWNERS
# All site config changes require review from the network-ops team
/sites/ @org/network-engineers
# Scripts require review from the automation team
/scripts/ @org/network-automation
```
This ensures that any PR modifying site configs automatically requests review from the designated peer group.
## 9. Security & Compliance Considerations
* **Least-privilege service account**: The Prisma SASE service account used by CI should have only the permissions required to push site configs (not full admin).
* **Audit trail**: Every change is tracked in Git history (who, when, what). PR discussions provide rationale.
* **No secrets in code**: All credentials stored in GitHub Secrets, never in YAML or scripts.
* **Rollback**: Revert a `prod` commit to restore the previous YAML, then re-run deploy. `do_site` is idempotent — it converges to the state defined in the YAML.
* **Site safety factor**: `do_site` defaults `--site-safety-factor` to 1, preventing accidental multi-site changes. Adjust only with explicit intent.
* **Branch protection**: Enforces that no single engineer can deploy without peer approval.
## 10. Recommendation
**Use the Python approach (prisma_config + prisma_sase SDK)** as your primary pipeline. It directly supports your existing YAML configs and `pull_site`/`do_site` workflow with minimal friction. The Terraform provider is a strong alternative if you want state management and plan/apply semantics, but requires converting your config format and is still in beta. Ansible adds unnecessary indirection for this specific use case unless you need to integrate with a broader Ansible-based operations framework.
## 11. Comparison Summary
**Python (prisma_config)**
* Config format: YAML (native to pull_site/do_site)
* Maturity: Stable (production)
* Dry run: No built-in dry-run (validate via schema + review)
* State management: None (converges to YAML state)
* Learning curve: Low (you already have this working)
* Best for: This exact use case
**Terraform (prismasdwan provider)**
* Config format: HCL (.tf files)
* Maturity: Beta (v6.6.1-beta.2)
* Dry run: `terraform plan` (excellent)
* State management: Yes (tfstate)
* Learning curve: Medium (HCL + state concepts)
* Best for: Greenfield or multi-tool IaC shops
**Ansible**
* Config format: YAML playbooks wrapping Python CLI
* Maturity: No native collection for Prisma SD-WAN site config
* Dry run: `--check` mode (limited for shell-wrapped commands)
* State management: None
* Learning curve: Medium
* Best for: Organizations already standardized on Ansible
