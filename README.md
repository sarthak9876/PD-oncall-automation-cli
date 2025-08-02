# PagerDuty Oncall Automation CLI

![PagerDuty Logo](https://assets.pagerduty.com/images/logos/pagerduty-logo-green.svg)

## Overview
This CLI tool automates the management of PagerDuty oncall rosters, making it easy to add or remove users, reassign incidents, and update schedules. It is designed for teams who want to streamline their PagerDuty operations and reduce manual effort.

---

## Problem Statement
Manually managing oncall rosters in PagerDuty is time-consuming and error-prone, especially for large teams. Adding/removing users, reassigning incidents, and updating schedules can be a real challenge. This tool automates:

- Adding users to oncall schedules and escalation policies
- Removing users from PagerDuty, safely reassigning their incidents
- Reassigning all active incidents to another user in the same escalation policy
- Ensuring no user is deleted while they still have incidents
- Updating schedules and policies

---

## Features
- **Bulk Add/Remove:** Add or remove multiple users in one go
- **Incident Reassignment:** Automatically reassigns incidents before deleting users
- **Flexible Input:** Accepts lists for users, names, roles, and policies
- **Safety Checks:** Prevents deletion if incidents are still assigned
- **Detailed Info:** Shows user details, teams, oncall status, and incidents

---

## Installation
1. Clone this repository:
   ```sh
   git clone <your-repo-url>
   cd <your-repo-folder>
   ```
2. Install dependencies:
   ```sh
   pip install -r requirements.txt
   ```

---

## Usage
### Get Info for Multiple Users
```sh
python main.py --action get-info --user user1@example.com user2@example.com
```

### Add Multiple Users with Different Roles
```sh
python main.py --action add \
  --user user1@sprinklr.com user2@sprinklr.com \
  --user-name "User One" "User Two" \
  --user-role responder manager \
  --policy POLICY_ID
```

### Remove Multiple Users Safely
```sh
python main.py --action remove --user user1@sprinklr.com user2@sprinklr.com --policy POLICY_ID
```

### API Token
For safety, you can pass the PagerDuty API token as an argument or set it as an environment variable:
```sh
export PAGERDUTY_API_TOKEN=your_token_here
```
Or use:
```sh
python main.py --pagerduty-api-token your_token_here ...
```

---

## How Incident Reassignment Works
When you remove a user, the script:
1. Checks for any active incidents assigned to that user
2. Finds another user in the same escalation policy
3. Reassigns all incidents to the alternative user
4. Deletes the user only after all incidents are reassigned

This ensures no incident is left unassigned and the oncall schedule remains healthy.

---

## Work in Progress
This tool is actively being developed. Planned improvements:
- More robust error handling and logging
- Support for schedule updates and advanced roster management
- Integration with other automation systems
- Better mapping between users, names, and roles for bulk operations

---

## Contributing & Feedback
Suggestions and contributions are welcome! Please open an issue or pull request. Your feedback will help make this tool more reliable and user-friendly.

---

## License
MIT
