"""
PagerDuty API Wrapper Class
=============================
Comprehensive wrapper for PagerDuty REST API v2, providing methods for:
  - User Management (create, get, delete)
  - Escalation Policy Management (add/remove users, update levels)
  - Schedule Management (add users, override shifts)
  - Incident Management (acknowledge, resolve, reassign)
  - Team Management (add users)
  - On-call Status Queries

All API calls use standard HTTP methods (GET, POST, PUT, DELETE).
Authentication: Bearer token (PAGERDUTY_API_TOKEN)
API Base: https://api.pagerduty.com
API Version: v2
"""

import requests
import time

class PagerDutyAPI:
    """
    PagerDuty API client for managing incidents, users, schedules, and policies.
    """
    BASE_URL = "https://api.pagerduty.com"

    def __init__(self, token):
        """Initialize API client with authentication token."""
        self.token = token
        self.headers = {
            "Authorization": f"Token token={token}",
            "Accept": "application/vnd.pagerduty+json;version=2",
            "Content-Type": "application/json",
        }

    # ========================================================================
    # USER MANAGEMENT METHODS
    # ========================================================================

    def get_user_by_email(self, email):
        """
        Retrieve user by email address.
        Returns first matching user or None if not found.
        """
        url = f"{self.BASE_URL}/users"
        params = {"query": email, "limit": 1}
        resp = requests.get(url, headers=self.headers, params=params)
        resp.raise_for_status()
        users = resp.json().get("users", [])
        return users[0] if users else None

    def get_user_by_id(self, user_id):
        """
        Retrieve user by PagerDuty user ID.
        Returns user object or None if not found.
        """
        url = f"{self.BASE_URL}/users/{user_id}"
        resp = requests.get(url, headers=self.headers)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json().get("user")

    def create_user(self, email, name, role):
        """
        Create a new PagerDuty user.
        
        Args:
            email: User email (unique identifier)
            name: Full name
            role: One of [admin, limited_user, user, restricted_access_user, read_only_access_user]
        
        Returns:
            User object with ID, name, email
        """
        url = f"{self.BASE_URL}/users"
        data = {
            "user": {
                "type": "user",
                "name": name,
                "email": email,
                "role": role,
                "time_zone": "Asia/Kolkata"
            }
        }
        resp = requests.post(url, headers=self.headers, json=data)
        if resp.status_code != 201:
            print(f"Error creating user {email}: {resp.status_code}")
            print(f"Response: {resp.text}")
            resp.raise_for_status()
        return resp.json()["user"]

    def delete_user(self, user_id):
        """
        Safely delete a user from PagerDuty.
        
        Multi-stage deletion process:
          Stage 1: Override user in all schedules (replace with next on-call)
          Stage 2: Override user in all escalation policies
          Stage 3: Verify user removed from schedules
          Stage 4: Verify user removed from escalation policies
          Stage 5: Delete user account
        
        This ensures no orphaned on-call assignments or incidents remain.
        """
        print(f"[Stage 1] Overriding user in all schedules...")
        self.override_user_in_all_schedules(user_id, avoid_user_ids=[user_id])
        print(f"[Stage 2] Overriding user in all escalation policies...")
        self.override_user_in_all_escalation_policies(user_id, avoid_user_ids=[user_id])
        print(f"[Stage 3] Checking if user is still present in any schedule...")
        if self.is_user_in_any_schedule(user_id):
            print(f"Cannot delete user {user_id}: still present in one or more schedules. Remove all references before deletion.")
            return False
        print(f"[Stage 4] Checking if user is still present in any escalation policy...")
        if self.is_user_in_any_escalation_policy(user_id):
            print(f"Cannot delete user {user_id}: still present in one or more escalation policies. Remove all references before deletion.")
            return False
        print(f"[Stage 5] Deleting user from PagerDuty...")
        url = f"{self.BASE_URL}/users/{user_id}"
        resp = requests.delete(url, headers=self.headers)
        resp.raise_for_status()
        print(f"User {user_id} deleted successfully.")
        return True

    def get_user_oncalls(self, user_id):
        """
        Get all on-call shifts for a user in all escalation policies/schedules.
        
        Returns list of oncall objects with:
          - escalation_policy: Policy details
          - schedule: Schedule details (if applicable)
          - start/end: Shift times
        """
        url = f"{self.BASE_URL}/oncalls"
        params = {
            "time_zone": "Asia/Kolkata",
            "limit": 100,
            "user_ids[]": user_id
        }
        resp = requests.get(url, headers=self.headers, params=params)
        resp.raise_for_status()
        return resp.json().get("oncalls", [])

    # ========================================================================
    # INCIDENT MANAGEMENT METHODS
    # ========================================================================

    def list_user_incidents(self, user_id):
        """
        Get all triggered/acknowledged incidents assigned to a user.
        
        Returns list of incident objects with:
          - id: Incident ID
          - title: Incident summary
          - status: 'triggered' or 'acknowledged'
          - escalation_policy: Policy managing this incident
        """
        url = f"{self.BASE_URL}/incidents"
        params = {'user_ids[]': user_id, 'statuses[]': ['triggered', 'acknowledged']}
        resp = requests.get(url, headers=self.headers, params=params)
        resp.raise_for_status()
        return resp.json().get('incidents', [])

    def acknowledge_incident(self, incident_id):
        """
        Acknowledge an incident (change status from 'triggered' to 'acknowledged').
        
        Used in auto-acknowledge workflows to prevent escalation.
        """
        url = f"{self.BASE_URL}/incidents/{incident_id}"
        data = {
            "incident": {
                "type": "incident",
                "status": "acknowledged"
            }
        }
        resp = requests.put(url, headers=self.headers, json=data)
        resp.raise_for_status()
        return resp.json().get('incident')

    def resolve_incident(self, incident_id):
        """
        Resolve an incident (change status to 'resolved').
        
        Used to close incidents that are no longer active.
        """
        url = f"{self.BASE_URL}/incidents/{incident_id}"
        data = {
            "incident": {
                "type": "incident",
                "status": "resolved"
            }
        }
        resp = requests.put(url, headers=self.headers, json=data)
        resp.raise_for_status()
        return resp.json().get('incident')

    def reassign_incident(self, incident_id, user_id):
        """
        Reassign an incident to a specific user.
        
        Args:
            incident_id: Incident to reassign
            user_id: Target user for assignment
        """
        url = f"{self.BASE_URL}/incidents/{incident_id}"
        data = {
            "incident": {
                "type": "incident",
                "assignments": [{"assignee": {"type": "user_reference", "id": user_id}}]
            }
        }
        resp = requests.put(url, headers=self.headers, json=data)
        resp.raise_for_status()
        return resp.json().get('incident')

    def reassign_incident_to_policy(self, incident_id, policy_id):
        """
        Reassign an incident to an escalation policy for round-robin distribution.
        
        When reassigned to a policy, PagerDuty automatically distributes the incident
        across all on-call users in the policy using its round-robin logic.
        
        This is preferred over reassigning to a specific user as it ensures:
        - Load balancing across team members
        - Automatic escalation if current user doesn't acknowledge
        - Better incident distribution
        
        Args:
            incident_id: Incident to reassign
            policy_id: Escalation policy for round-robin assignment
        """
        url = f"{self.BASE_URL}/incidents/{incident_id}"
        data = {
            "incident": {
                "type": "incident",
                "escalation_policy": {
                    "id": policy_id,
                    "type": "escalation_policy_reference"
                }
            }
        }
        resp = requests.put(url, headers=self.headers, json=data)
        resp.raise_for_status()
        return resp.json().get('incident')

    # ========================================================================
    # ESCALATION POLICY MANAGEMENT METHODS
    # ========================================================================

    def list_escalation_policies(self):
        """
        Fetch all escalation policies in the account.
        
        Handles pagination automatically (fetches all policies).
        
        Returns list of policy objects with:
          - id: Policy ID
          - summary: Policy name
          - escalation_rules: List of escalation levels
        """
        policies = []
        offset = 0
        limit = 100
        while True:
            url = f"{self.BASE_URL}/escalation_policies"
            params = {"offset": offset, "limit": limit}
            resp = requests.get(url, headers=self.headers, params=params)
            resp.raise_for_status()
            batch = resp.json().get("escalation_policies", [])
            policies.extend(batch)
            if len(batch) < limit:
                break
            offset += limit
        return policies
        policies = []
        offset = 0
        limit = 100
        while True:
            url = f"{self.BASE_URL}/escalation_policies"
            params = {"offset": offset, "limit": limit}
            resp = requests.get(url, headers=self.headers, params=params)
            resp.raise_for_status()
            batch = resp.json().get("escalation_policies", [])
            policies.extend(batch)
            if len(batch) < limit:
                break
            offset += limit
        return policies

    def get_escalation_policy_with_targets(self, policy_id):
        url = f"{self.BASE_URL}/escalation_policies/{policy_id}"
        params = {"include[]": "targets"}
        resp = requests.get(url, headers=self.headers, params=params)
        resp.raise_for_status()
        return resp.json()["escalation_policy"]

    def get_escalation_policy(self, policy_id):
        url = f"{self.BASE_URL}/escalation_policies/{policy_id}"
        resp = requests.get(url, headers=self.headers)
        resp.raise_for_status()
        return resp.json()["escalation_policy"]

    def update_escalation_policy(self, policy_id, updated_policy):
        url = f"{self.BASE_URL}/escalation_policies/{policy_id}"
        resp = requests.put(url, headers=self.headers, json={'escalation_policy': updated_policy})
        resp.raise_for_status()
        return resp.json()['escalation_policy']

    def list_services(self):
        url = f"{self.BASE_URL}/services"
        resp = requests.get(url, headers=self.headers)
        resp.raise_for_status()
        return resp.json().get("services", [])

    def get_policy_id_from_service(self, service_name):
        for srv in self.list_services():
            if srv["summary"].lower() == service_name.lower():
                return srv["escalation_policy"]["id"]
        return None

    def list_user_incidents(self, user_id):
        url = f"{self.BASE_URL}/incidents"
        params = {'user_ids[]': user_id, 'statuses[]': ['triggered', 'acknowledged']}
        resp = requests.get(url, headers=self.headers, params=params)
        resp.raise_for_status()
        return resp.json().get('incidents', [])

    def list_teams(self):
        teams = []
        offset = 0
        limit = 100
        while True:
            url = f"{self.BASE_URL}/teams"
            params = {"offset": offset, "limit": limit}
            resp = requests.get(url, headers=self.headers, params=params)
            resp.raise_for_status()
            batch = resp.json().get("teams", [])
            teams.extend(batch)
            if len(batch) < limit:
                break
            offset += limit
        return teams

    def get_team_users(self, team_id):
        url = f"{self.BASE_URL}/teams/{team_id}/users"
        resp = requests.get(url, headers=self.headers)
        resp.raise_for_status()
        return resp.json().get("users", [])

    def get_team_by_name(self, team_name):
        """
        Get team details by name.
        """
        teams = self.list_teams()
        for team in teams:
            if team.get('summary', '').lower() == team_name.lower():
                return team
        return None

    def get_team_by_id(self, team_id):
        """
        Get team details by ID.
        """
        url = f"{self.BASE_URL}/teams/{team_id}"
        resp = requests.get(url, headers=self.headers)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json().get("team")

    def add_user_to_team(self, team_id, user_id):
        """
        Add a user to a team.
        Uses the teams/{id}/users endpoint with proper payload.
        """
        url = f"{self.BASE_URL}/teams/{team_id}/users"
        data = {
            "users": [
                {
                    "id": user_id,
                    "type": "user_reference"
                }
            ]
        }
        try:
            resp = requests.post(url, headers=self.headers, json=data)
            
            if resp.status_code == 400:
                # User might already be in team or invalid team
                error_msg = resp.json().get('error', {}).get('message', '')
                if 'already' in error_msg.lower():
                    return False
                print(f"Error details: {error_msg}")
                return False
            
            if resp.status_code == 404:
                print(f"Team ID {team_id} not found or endpoint not accessible")
                return False
            
            if resp.status_code == 201 or resp.status_code == 200:
                return True
            
            resp.raise_for_status()
            return True
        except Exception as e:
            print(f"Failed to add user to team: {str(e)}")
            return False

    # For "add to policy" and "remove from policy" logic:
    def add_user_to_policy(self, policy, user_id, role, rule_index=None):
        """
        Add user to a specific escalation rule (level) in a policy.
        If rule_index is None, adds to the last rule (bottom).
        """
        if not policy['escalation_rules']:
            print("No escalation rules on policy.")
            return False
        
        # Use specified rule or default to last rule
        if rule_index is None:
            rule_index = len(policy['escalation_rules']) - 1
        elif rule_index >= len(policy['escalation_rules']):
            print(f"Rule index {rule_index} out of range. Policy has {len(policy['escalation_rules'])} rules.")
            return False
        
        target = {"id": user_id, "type": "user_reference"}
        targets = policy['escalation_rules'][rule_index].get('targets', [])
        
        if target not in targets:
            targets.append(target)
            policy['escalation_rules'][rule_index]['targets'] = targets
            return True
        return False

    def list_escalation_rules(self, policy_id):
        """
        List all escalation rules (levels) in a policy with their details.
        """
        policy = self.get_escalation_policy(policy_id)
        rules = []
        for idx, rule in enumerate(policy.get('escalation_rules', [])):
            rule_info = {
                'index': idx,
                'id': rule.get('id'),
                'escalation_delay_in_minutes': rule.get('escalation_delay_in_minutes'),
                'targets': rule.get('targets', [])
            }
            rules.append(rule_info)
        return rules

    def list_schedules(self):
        """
        List all schedules in the account.
        """
        schedules = []
        offset = 0
        limit = 100
        while True:
            url = f"{self.BASE_URL}/schedules"
            params = {"offset": offset, "limit": limit}
            resp = requests.get(url, headers=self.headers, params=params)
            resp.raise_for_status()
            batch = resp.json().get("schedules", [])
            schedules.extend(batch)
            if len(batch) < limit:
                break
            offset += limit
        return schedules

    def get_schedule_by_name(self, schedule_name):
        """
        Get schedule details by name.
        """
        schedules = self.list_schedules()
        for sched in schedules:
            if sched.get('summary', '').lower() == schedule_name.lower():
                # Fetch full schedule with layers
                url = f"{self.BASE_URL}/schedules/{sched['id']}"
                resp = requests.get(url, headers=self.headers)
                resp.raise_for_status()
                return resp.json().get('schedule')
        return None

    def add_user_to_schedule_layer(self, schedule_id, user_id, start_time=None, end_time=None):
        """
        Add user to a schedule layer with optional time window (ISO 8601 format).
        If no time window, adds to the entire schedule layer.
        start_time: ISO 8601 format (e.g., "2025-11-27T06:00:00+05:30")
        end_time: ISO 8601 format (e.g., "2025-11-27T15:00:00+05:30")
        """
        url = f"{self.BASE_URL}/schedules/{schedule_id}"
        resp = requests.get(url, headers=self.headers)
        resp.raise_for_status()
        schedule = resp.json().get('schedule', {})
        
        layers = schedule.get('schedule_layers', [])
        if not layers:
            print(f"Schedule {schedule_id} has no layers.")
            return False
        
        # Add user to the first (or only) layer
        layer = layers[0]
        
        # Create a new rendered schedule entry for this user
        user_entry = {
            "user": {
                "id": user_id,
                "type": "user_reference"
            }
        }
        
        if start_time and end_time:
            user_entry["start"] = start_time
            user_entry["end"] = end_time
        
        # Add to rendered schedule entries (this is how PagerDuty handles time-based assignments)
        if 'rendered_schedule_entries' not in layer:
            layer['rendered_schedule_entries'] = []
        
        layer['rendered_schedule_entries'].append(user_entry)
        
        # Update the schedule
        update_data = {'schedule': schedule}
        update_resp = requests.put(url, headers=self.headers, json=update_data)
        
        if update_resp.status_code != 200:
            print(f"Error adding user to schedule: {update_resp.status_code}")
            print(f"Response: {update_resp.text}")
            return False
        
        return True

    def list_schedule_users(self, schedule_id):
        """
        List all users assigned to a schedule.
        """
        url = f"{self.BASE_URL}/schedules/{schedule_id}"
        resp = requests.get(url, headers=self.headers)
        resp.raise_for_status()
        schedule = resp.json().get('schedule', {})
        
        users = set()
        for layer in schedule.get('schedule_layers', []):
            for user_ref in layer.get('users', []):
                users.add(user_ref.get('id'))
        
        return list(users)

    def remove_user_from_policy(self, policy, user_id):
        changed = False
        # Remove user from escalation rules
        for rule in policy.get('escalation_rules', []):
            before = len(rule.get('targets', []))
            rule['targets'] = [t for t in rule.get('targets', []) if not (t.get('type') == 'user' and t.get('id') == user_id)]
            after = len(rule.get('targets', []))
            if after < before:
                changed = True
        return changed

    def reassign_incident(self, incident_id, user_id):
        """Reassign incident to a specific user."""
        url = f"{self.BASE_URL}/incidents/{incident_id}"
        data = {
            "incident": {
                "type": "incident",
                "assignments": [{"assignee": {"type": "user_reference", "id": user_id}}]
            }
        }
        resp = requests.put(url, headers=self.headers, json=data)
        resp.raise_for_status()
        return resp.json().get('incident')

    def reassign_incident_to_policy(self, incident_id, policy_id):
        """Reassign incident to an escalation policy for round-robin distribution.
        When reassigned to a policy, PagerDuty automatically distributes the incident
        across all users in the policy using round-robin logic.
        """
        url = f"{self.BASE_URL}/incidents/{incident_id}"
        data = {
            "incident": {
                "type": "incident",
                "escalation_policy": {
                    "id": policy_id,
                    "type": "escalation_policy_reference"
                }
            }
        }
        resp = requests.put(url, headers=self.headers, json=data)
        resp.raise_for_status()
        return resp.json().get('incident')

    def get_policy_users(self, policy_id):
        policy = self.get_escalation_policy_with_targets(policy_id)
        users = set()
        for rule in policy.get('escalation_rules', []):
            for target in rule.get('targets', []):
                if target['type'] == 'user_reference':
                    users.add(target['id'])
        return list(users)

    def remove_user_from_all_schedules(self, user_id):
        url = f"{self.BASE_URL}/schedules"
        resp = requests.get(url, headers=self.headers)
        resp.raise_for_status()
        schedules = resp.json().get("schedules", [])
        removed_from_any = False
        for sched in schedules:
            sched_id = sched['id']
            # Get schedule details
            sched_url = f"{self.BASE_URL}/schedules/{sched_id}"
            sched_resp = requests.get(sched_url, headers=self.headers)
            sched_resp.raise_for_status()
            sched_obj = sched_resp.json().get('schedule', {})
            # Remove user from schedule layers
            layers = sched_obj.get('schedule_layers', [])
            for layer in layers:
                orig_users = layer.get('users', [])
                new_users = [u for u in orig_users if u.get('user', {}).get('id') != user_id]
                if len(new_users) < len(orig_users):
                    layer['users'] = new_users
                    removed_from_any = True
            # If any change, update schedule
            if removed_from_any:
                update_url = f"{self.BASE_URL}/schedules/{sched_id}"
                update_data = {"schedule": sched_obj}
                update_resp = requests.put(update_url, headers=self.headers, json=update_data)
                update_resp.raise_for_status()
                print(f"Removed user {user_id} from schedule: {sched.get('summary', sched_id)} (ID: {sched_id})")
        return removed_from_any

    def override_user_in_all_schedules(self, user_id, avoid_user_ids=None):
        if avoid_user_ids is None:
            avoid_user_ids = [user_id]
        url = f"{self.BASE_URL}/schedules"
        resp = requests.get(url, headers=self.headers)
        resp.raise_for_status()
        schedules = resp.json().get("schedules", [])
        for sched in schedules:
            sched_id = sched['id']
            sched_url = f"{self.BASE_URL}/schedules/{sched_id}"
            sched_resp = requests.get(sched_url, headers=self.headers)
            sched_resp.raise_for_status()
            sched_obj = sched_resp.json().get('schedule', {})
            layers = sched_obj.get('schedule_layers', [])
            changed = False
            for idx, layer in enumerate(layers):
                orig_users = layer.get('users', [])
                user_ids_in_layer = [u.get('user', {}).get('id') for u in orig_users]
                if user_id in user_ids_in_layer:
                    # Try to find replacement in current layer
                    replacement = next((u for u in orig_users if u.get('user', {}).get('id') not in avoid_user_ids), None)
                    # If not found, try previous layer
                    if not replacement and idx > 0:
                        prev_layer_users = layers[idx-1].get('users', [])
                        replacement = next((u for u in prev_layer_users if u.get('user', {}).get('id') not in avoid_user_ids), None)
                    # If not found, try next layer
                    if not replacement and idx < len(layers)-1:
                        next_layer_users = layers[idx+1].get('users', [])
                        replacement = next((u for u in next_layer_users if u.get('user', {}).get('id') not in avoid_user_ids), None)
                    if replacement:
                        layer['users'] = [replacement if u.get('user', {}).get('id') == user_id else u for u in orig_users]
                        changed = True
                        print(f"Replaced user {user_id} with {replacement.get('user', {}).get('id')} in schedule: {sched.get('summary', sched_id)} (ID: {sched_id})")
                    else:
                        print(f"No replacement found for user {user_id} in schedule: {sched.get('summary', sched_id)} (ID: {sched_id})")
            if changed:
                update_url = f"{self.BASE_URL}/schedules/{sched_id}"
                update_data = {"schedule": sched_obj}
                update_resp = requests.put(update_url, headers=self.headers, json=update_data)
                update_resp.raise_for_status()
        return True

    def override_user_in_all_escalation_policies(self, user_id, avoid_user_ids=None):
        if avoid_user_ids is None:
            avoid_user_ids = [user_id]
        policies = self.list_escalation_policies()
        for policy in policies:
            changed = False
            for rule in policy.get('escalation_rules', []):
                orig_targets = rule.get('targets', [])
                user_ids_in_rule = [t.get('id') for t in orig_targets if t.get('type') == 'user_reference']
                if user_id in user_ids_in_rule:
                    # Find replacement user in the same rule not in avoid_user_ids
                    replacement = next((t for t in orig_targets if t.get('type') == 'user_reference' and t.get('id') not in avoid_user_ids), None)
                    if replacement:
                        rule['targets'] = [replacement if (t.get('type') == 'user_reference' and t.get('id') == user_id) else t for t in orig_targets]
                        changed = True
                        print(f"Replaced user {user_id} with {replacement.get('id')} in escalation policy: {policy.get('summary', policy['id'])} (ID: {policy['id']})")
                    else:
                        print(f"No replacement found for user {user_id} in escalation policy: {policy.get('summary', policy['id'])} (ID: {policy['id']})")
            if changed:
                self.update_escalation_policy(policy['id'], policy)
        return True

    def is_user_in_any_schedule(self, user_id):
        schedules = self.list_schedules()  # This handles pagination properly
        for sched in schedules:
            sched_id = sched['id']
            sched_url = f"{self.BASE_URL}/schedules/{sched_id}"
            sched_resp = requests.get(sched_url, headers=self.headers)
            sched_resp.raise_for_status()
            sched_obj = sched_resp.json().get('schedule', {})
            layers = sched_obj.get('schedule_layers', [])
            for layer in layers:
                for u in layer.get('users', []):
                    if u.get('user', {}).get('id') == user_id:
                        return True
        return False

    def is_user_in_any_escalation_policy(self, user_id):
        policies = self.list_escalation_policies()
        for policy in policies:
            for rule in policy.get('escalation_rules', []):
                for t in rule.get('targets', []):
                    if t.get('type') == 'user_reference' and t.get('id') == user_id:
                        return True
        return False

    def delete_user(self, user_id):
        print(f"[Stage 1] Overriding user in all schedules...")
        self.override_user_in_all_schedules(user_id, avoid_user_ids=[user_id])
        print(f"[Stage 2] Overriding user in all escalation policies...")
        self.override_user_in_all_escalation_policies(user_id, avoid_user_ids=[user_id])
        print(f"[Stage 3] Checking if user is still present in any schedule...")
        if self.is_user_in_any_schedule(user_id):
            print(f"Cannot delete user {user_id}: still present in one or more schedules. Remove all references before deletion.")
            return False
        print(f"[Stage 4] Checking if user is still present in any escalation policy...")
        if self.is_user_in_any_escalation_policy(user_id):
            print(f"Cannot delete user {user_id}: still present in one or more escalation policies. Remove all references before deletion.")
            return False
        print(f"[Stage 5] Deleting user from PagerDuty...")
        url = f"{self.BASE_URL}/users/{user_id}"
        resp = requests.delete(url, headers=self.headers)
        resp.raise_for_status()
        print(f"User {user_id} deleted successfully.")
        return True


