import requests
import time

class PagerDutyAPI:
    def acknowledge_incident(self, incident_id):
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
    BASE_URL = "https://api.pagerduty.com"

    def __init__(self, token):
        self.token = token
        self.headers = {
            "Authorization": f"Token token={token}",
            "Accept": "application/vnd.pagerduty+json;version=2",
            "Content-Type": "application/json",
        }

    def get_user_by_email(self, email):
        url = f"{self.BASE_URL}/users"
        params = {"query": email, "limit": 1}
        resp = requests.get(url, headers=self.headers, params=params)
        resp.raise_for_status()
        users = resp.json().get("users", [])
        return users[0] if users else None

    def get_user_by_id(self, user_id):
        url = f"{self.BASE_URL}/users/{user_id}"
        resp = requests.get(url, headers=self.headers)
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        return resp.json().get("user")

    def create_user(self, email, name, role):
        url = f"{self.BASE_URL}/users"
        data = {
            "user": {
                "type": "user",
                "name": name,
                "email": email,
                "role": role,
            }
        }
        resp = requests.post(url, headers=self.headers, json=data)
        resp.raise_for_status()
        return resp.json()["user"]

    def get_user_oncalls(self, user_id):
        url = f"{self.BASE_URL}/oncalls"
        params = {
            "time_zone": "Asia/Kolkata",
            "limit": 100,
            "user_ids[]": user_id
        }
        resp = requests.get(url, headers=self.headers, params=params)
        resp.raise_for_status()
        return resp.json().get("oncalls", [])

    def list_escalation_policies(self):
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

    # For "add to policy" and "remove from policy" logic:
    def add_user_to_policy(self, policy, user_id, role, as_first=False):
        if not policy['escalation_rules']:
            print("No escalation rules on policy.")
            return False
        target = {"id": user_id, "type": "user_reference"}
        # Insert at L1 (top) for "user"/"limited_user", else at end
        if as_first:
            if target not in policy['escalation_rules'][0]['escalation_targets']:
                policy['escalation_rules'][0]['escalation_targets'].insert(0, target)
                return True
        else:
            if target not in policy['escalation_rules'][-1]['escalation_targets']:
                policy['escalation_rules'][-1]['escalation_targets'].append(target)
                return True
        return False

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

