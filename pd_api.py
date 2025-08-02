import requests
import time

class PagerDutyAPI:
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
        for rule in policy['escalation_rules']:
            before = len(rule['escalation_targets'])
            rule['escalation_targets'] = [
                t for t in rule['escalation_targets'] if not (t['type'] == 'user_reference' and t['id'] == user_id)
            ]
            if len(rule['escalation_targets']) != before:
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

    def delete_user(self, user_id):
        url = f"{self.BASE_URL}/users/{user_id}"
        resp = requests.delete(url, headers=self.headers)
        resp.raise_for_status()
        return True

