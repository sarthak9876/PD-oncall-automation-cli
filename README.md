# PagerDuty Oncall Automation CLI

![PagerDuty Logo](PagerDuty-Logo.png)

## Overview

This comprehensive CLI toolkit automates PagerDuty on-call roster management, incident handling, and user lifecycle operations. Designed for teams managing large-scale incident response, it provides production-ready tools for:

- **User Management:** Create, retrieve, and safely delete users with automatic incident reassignment
- **Escalation Policy Management:** Add/remove users from escalation levels with interactive selection
- **Schedule Management:** Assign users to on-call schedules with optional time windows (ISO 8601)
- **Incident Management:** Auto-acknowledge/resolve incidents with round-robin distribution
- **Safety-First Deletion:** Multi-stage user removal preventing orphaned assignments

---

## Problem Statement

Manually managing PagerDuty on-call rosters is time-consuming, error-prone, and risky:

- Adding/removing users across multiple escalation levels requires manual updates
- Deleting users with active incidents can leave critical incidents unassigned
- Manual incident reassignment is slow and error-prone
- No automatic acknowledgment/resolution capabilities for automation workflows

This toolkit solves these challenges with **safe, automated operations** and **safety checks** at every step.

---

## Table of Contents

1. [Installation](#installation)
2. [Configuration](#configuration)
3. [Core Scripts](#core-scripts)
   - [main.py](#mainpy-primary-cli-tool)
   - [pd_api.py](#pd_apipy-api-wrapper)
   - [ack_resolve_alerts.py](#ack_resolve_alertspy-incident-automation)
4. [Usage Examples](#usage-examples)
5. [Safety Features](#safety-features)
6. [API Token Management](#api-token-management)
7. [Contributing](#contributing)

---

## Installation

### Prerequisites
- Python 3.7+
- pip package manager

### Setup Steps

1. Clone this repository:
   ```sh
   git clone <your-repo-url>
   cd PD-oncall-automation-cli
   ```

2. Install dependencies:
   ```sh
   pip install -r requirements.txt
   ```

3. Configure your PagerDuty API token (see [Configuration](#configuration) section)

---

## Configuration

### API Token Setup

The tool loads API tokens in this priority order:

1. **CLI Argument** (highest priority): `--pagerduty-api-token YOUR_TOKEN`
2. **Environment Variable**: `PAGERDUTY_API_TOKEN=YOUR_TOKEN`
3. **Config File** (lowest priority): `config.yaml`

#### Option 1: Environment Variable (Recommended)
```sh
export PAGERDUTY_API_TOKEN="your_pagerduty_api_token"
```

#### Option 2: CLI Argument
```sh
python main.py --action get-info --user user@example.com --pagerduty-api-token "your_token"
```

#### Option 3: Config File
Create/edit `config.yaml`:
```yaml
pagerduty_api_token: "your_pagerduty_api_token"
# default_policy_id: "POLICY_ID"  # Optional: Set default escalation policy
```

⚠️ **SECURITY WARNING:** Never commit `config.yaml` with API tokens! The `.gitignore` file already excludes it.

### Optional Configuration

Set a default escalation policy in `config.yaml` to avoid specifying `--policy` repeatedly:
```yaml
default_policy_id: "PFNVVHZ"
```

---

## Core Scripts

### main.py - Primary CLI Tool

**Purpose:** Command-line interface for user management, escalation policy operations, and on-call queries.

**Supported Actions:**

#### 1. GET-INFO Action
Retrieve comprehensive information about one or more users.

**Usage:**
```sh
python main.py --action get-info --user user@sprinklr.com
```

**What It Displays:**
- User basic info (name, email, ID, role)
- Team memberships with IDs
- Current on-call status in escalation policies and schedules
- Active assigned incidents with status

**Example Output:**
```
User: John Doe (john.doe@sprinklr.com)
ID: PXXXXXXX | Role: user

Teams:
  • DevOps Team (PXXXXXXX)
  • SRE Team (PXXXXXXX)

On-Call Status:
  • Production Escalation Policy (Level 1)
  • Backend Schedules (Active: 2025-01-07 to 2025-01-14)

Active Incidents:
  • INC-001: Database Connection Timeout (triggered)
  • INC-002: API Server Down (acknowledged)
```

---

#### 2. ADD Action
Create a new user or configure an existing user with team, schedule, and escalation policy assignments.

**Basic Usage:**
```sh
python main.py --action add --user user@sprinklr.com --user-name "John Doe"
```

**With Team Assignment:**
```sh
python main.py --action add \
  --user user@sprinklr.com \
  --user-name "John Doe" \
  --team "DevOps Team"
```

**With Escalation Policy:**
```sh
python main.py --action add \
  --user user@sprinklr.com \
  --user-name "John Doe" \
  --policy POLICY_ID
```
If `--level` is not specified, the tool will interactively prompt you to select from available escalation levels.

**With Schedule Assignment (Time Window):**
```sh
python main.py --action add \
  --user user@sprinklr.com \
  --user-name "John Doe" \
  --schedule "On-Call Schedule" \
  --start-time "2025-01-07T09:00:00Z" \
  --end-time "2025-01-14T09:00:00Z"
```

**Add to Multiple Resources:**
```sh
python main.py --action add \
  --user user@sprinklr.com \
  --user-name "John Doe" \
  --team "DevOps Team" \
  --policy POLICY_ID \
  --level 1
```

**Arguments:**
- `--user` (required): User email
- `--user-name` (required): Full name
- `--team` (optional): Team name
- `--policy` (optional): Escalation policy ID or name
- `--level` (optional): Escalation level (1-5). If omitted, interactive selection
- `--schedule` (optional): Schedule name
- `--start-time` (optional): ISO 8601 start time for schedule assignment
- `--end-time` (optional): ISO 8601 end time for schedule assignment
- `--pagerduty-api-token` (optional): API token

**Notes:**
- Schedule and policy are **mutually exclusive** (use one or the other, not both)
- Team assignment is optional but recommended
- Email must be from authorized domain (e.g., @sprinklr.com)

---

#### 3. REMOVE Action
Safely delete a user with multi-stage incident reassignment and verification.

**Basic Usage:**
```sh
python main.py --action remove --user user@sprinklr.com
```

**With Specific Escalation Policy:**
```sh
python main.py --action remove --user user@sprinklr.com --policy POLICY_ID
```

**What Happens During Removal:**

The tool executes a **5-stage deletion process** to ensure data integrity:

1. **Status Check:** Identify all on-call assignments and active incidents
2. **Policy Removal:** Remove user from all escalation policy levels
3. **Incident Reassignment:** Automatically reassign incidents to the escalation policy (enables round-robin distribution)
4. **Verification:** Confirm user removed from all policies and schedules
5. **User Deletion:** Delete the user account after all safety checks pass

**Example Output:**
```
[Stage 1] Removing user from escalation policies...
[Stage 2] Reassigning 3 incidents to Production Escalation Policy for round-robin...
  ✓ Reassigned INC-001 to Production Escalation Policy
  ✓ Reassigned INC-002 to Production Escalation Policy
  ✓ Reassigned INC-003 to Production Escalation Policy
[Stage 3] Verifying user not in any escalation policy...
[Stage 4] User successfully deleted from PagerDuty
```

**Arguments:**
- `--user` (required): User email or ID
- `--policy` (optional): Specific policy to remove from
- `--pagerduty-api-token` (optional): API token

---

### pd_api.py - API Wrapper

**Purpose:** Encapsulates all PagerDuty REST API v2 interactions, providing a clean Python interface.

**Key Features:**

- **User Management:** Create, retrieve, delete users safely
- **Escalation Policy Operations:** Add/remove users from escalation levels
- **Schedule Management:** Assign users with optional time windows
- **Incident Management:** Acknowledge, resolve, and reassign incidents
- **Team Operations:** Add users to teams with proper payload formatting
- **On-Call Queries:** Check current on-call status across policies and schedules

**Main Methods:**

```python
# User Operations
get_user_by_email(email)                    # Get user by email
get_user_by_id(user_id)                     # Get user by ID
create_user(email, name, role)              # Create new user
delete_user(user_id)                        # Multi-stage deletion
get_user_oncalls(user_id)                   # Get on-call shifts

# Escalation Policy Management
list_escalation_policies()                  # Get all policies
get_escalation_policy(policy_id)            # Get single policy
add_user_to_policy(policy, user_id, role, level)  # Add to escalation level
remove_user_from_policy(policy, user_id)   # Remove from all levels
override_user_in_all_escalation_policies()  # Replace user in policies

# Schedule Management
list_schedules()                            # Get all schedules
get_schedule_by_name(schedule_name)         # Find schedule
add_user_to_schedule_layer()                # Assign to schedule
override_user_in_all_schedules()            # Replace user in schedules

# Incident Management
list_user_incidents(user_id)                # Get assigned incidents
acknowledge_incident(incident_id)           # Mark as acknowledged
resolve_incident(incident_id)               # Mark as resolved
reassign_incident(incident_id, user_id)    # Assign to specific user
reassign_incident_to_policy(incident_id, policy_id)  # Assign to policy (round-robin)

# Team Management
list_teams()                                # Get all teams
add_user_to_team(team_id, user_id)         # Add user to team
```

**Authentication:**
- All API calls use Bearer token authentication
- Base URL: `https://api.pagerduty.com`
- API Version: v2

---

### ack_resolve_alerts.py - Incident Automation

**Purpose:** Standalone utility for auto-acknowledging or batch-resolving incidents.

**Ideal For:**
- Automation workflows that need to acknowledge incidents
- Batch incident resolution
- Integration with external monitoring systems
- Preventing unnecessary escalations during known maintenance windows

**Two Operating Modes:**

#### Mode 1: Auto-Acknowledge (Continuous Monitoring)
Continuously monitors and auto-acknowledges triggered incidents for a user.

**Usage:**
```sh
python ack_resolve_alerts.py --action ack --user user@sprinklr.com --interval 10
```

**What It Does:**
1. Fetches all triggered incidents for the user
2. Auto-acknowledges any "triggered" incidents (prevents escalation)
3. Tracks already-acknowledged incidents to avoid duplicates
4. Sleeps for specified interval (default: 10 seconds)
5. Repeats indefinitely (run in background with `nohup` or `screen`)

**Run in Background:**
```sh
nohup python ack_resolve_alerts.py --action ack --user user@sprinklr.com --interval 10 > ack.log 2>&1 &
```

**Arguments:**
- `--action ack` (required): Set to "ack"
- `--user` (required): User email or ID
- `--interval` (optional): Poll interval in seconds (default: 10)

---

#### Mode 2: Batch Resolve (One-Time)
One-time batch resolution of all incidents for a user with optional severity filtering.

**Usage:**
```sh
python ack_resolve_alerts.py --action resolve --user user@sprinklr.com
```

**With Severity Filter:**
```sh
python ack_resolve_alerts.py --action resolve --user user@sprinklr.com --severity critical
```

**What It Does:**
1. Fetches all triggered/acknowledged incidents for the user
2. Filters by severity if specified
3. Resolves each incident
4. Exits after completion

**Arguments:**
- `--action resolve` (required): Set to "resolve"
- `--user` (required): User email or ID
- `--severity` (optional): Filter by severity (critical, high, medium, low)

---

## Usage Examples

### Complete Onboarding Workflow

Add a new team member with all necessary assignments:

```sh
# Step 1: Create user and add to team
python main.py --action add \
  --user john.doe@sprinklr.com \
  --user-name "John Doe" \
  --team "DevOps Team"

# Step 2: Add to escalation policy with interactive level selection
python main.py --action add \
  --user john.doe@sprinklr.com \
  --policy PFNVVHZ

# Step 3: Verify setup
python main.py --action get-info --user john.doe@sprinklr.com
```

### Scheduled On-Call Assignment

Assign user to schedule for a specific time period:

```sh
python main.py --action add \
  --user oncall@sprinklr.com \
  --schedule "Primary On-Call" \
  --start-time "2025-01-15T09:00:00Z" \
  --end-time "2025-01-22T09:00:00Z"
```

### Safe User Offboarding

Remove user with automatic incident reassignment:

```sh
# Remove with automatic incident reassignment to escalation policy
python main.py --action remove --user departing.user@sprinklr.com --policy PFNVVHZ

# Verify user is removed
python main.py --action get-info --user departing.user@sprinklr.com
```

### Incident Automation

Auto-acknowledge incidents during maintenance windows:

```sh
# Terminal 1: Start continuous auto-acknowledge
python ack_resolve_alerts.py --action ack --user oncall@sprinklr.com --interval 5

# Terminal 2 (later): Batch resolve all critical incidents
python ack_resolve_alerts.py --action resolve --user oncall@sprinklr.com --severity critical
```

---

## Safety Features

### Multi-Stage User Deletion

When removing a user, the tool ensures:

1. **Incident Identification:** Locates all incidents assigned to the user
2. **Policy Removal:** Removes user from all escalation policy levels
3. **Incident Reassignment:** Reassigns incidents to escalation policies (enables automatic distribution)
4. **Verification:** Confirms user removed from all on-call assignments
5. **Safe Deletion:** Deletes user only after all safety checks pass

### Round-Robin Incident Distribution

Instead of assigning incidents to specific users, the tool reassigns to escalation policies. This enables:

- **Automatic Distribution:** PagerDuty automatically routes incidents through escalation levels
- **Load Balancing:** Incidents distributed across available team members
- **No Orphaned Incidents:** All incidents remain assigned and acknowledged

### Error Handling

- Token validation before operations
- User verification with helpful error messages
- HTTP status code checking with detailed failure diagnostics
- Graceful handling of missing resources (404 responses)

---

## API Token Management

### Token Priority

The tool checks for API tokens in this order:

1. `--pagerduty-api-token` CLI argument
2. `PAGERDUTY_API_TOKEN` environment variable
3. `pagerduty_api_token` in `config.yaml`

### Securing Your Token

**DO NOT:**
- Commit `config.yaml` to version control (already in `.gitignore`)
- Hardcode tokens in scripts
- Share tokens in emails or chat

**DO:**
- Use environment variables in production
- Rotate tokens regularly
- Use `--pagerduty-api-token` for temporary operations
- Keep `config.yaml` locally only (excluded from git)

### Generate PagerDuty API Token

1. Log in to PagerDuty
2. Go to **User Profile** → **API Access** → **API Tokens**
3. Click **Create Token**
4. Copy the token and store securely

---

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch
3. Make your changes with proper documentation
4. Submit a pull request

For bug reports or feature requests, open an issue with:
- Clear description
- Steps to reproduce (for bugs)
- Expected vs. actual behavior

---

## License

MIT License - See LICENSE file for details

---

## Support

For issues, questions, or suggestions:
- Open an GitHub issue
- Check existing documentation
- Review code comments for implementation details

**Last Updated:** January 2025
