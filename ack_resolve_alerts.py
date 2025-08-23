import sys
import os
import yaml
from pd_api import PagerDutyAPI

def load_config():
    config = {}
    if os.path.exists("config.yaml"):
        with open("config.yaml", "r") as f:
            config = yaml.safe_load(f)
    pd_token = os.environ.get("PAGERDUTY_API_TOKEN") or config.get("pagerduty_api_token")
    if not pd_token:
        print("PagerDuty API token missing (env variable or config.yaml)")
        sys.exit(1)
    return pd_token

def acknowledge_incidents_loop(user_ref, poll_interval=10):
    import time
    pd_token = load_config()
    pd = PagerDutyAPI(pd_token)
    # Get user
    if "@" in user_ref:
        user = pd.get_user_by_email(user_ref)
    else:
        user = pd.get_user_by_id(user_ref)
    if not user:
        print(f"User not found: {user_ref}")
        return
    user_id = user['id']
    print(f"Monitoring incidents for user: {user.get('name')} ({user.get('email')})")
    already_ack = set()
    while True:
        incidents = pd.list_user_incidents(user_id)
        for inc in incidents:
            inc_id = inc['id']
            inc_title = inc.get('title', '')
            inc_status = inc.get('status', '')
            if inc_status == 'triggered' and inc_id not in already_ack:
                try:
                    pd.acknowledge_incident(inc_id)
                    print(f"Acknowledged incident: {inc_id} ({inc_title})")
                    already_ack.add(inc_id)
                except Exception as e:
                    print(f"Failed to acknowledge {inc_id}: {e}")
        time.sleep(poll_interval)

def resolve_incidents(user_ref, severity=None):
    pd_token = load_config()
    pd = PagerDutyAPI(pd_token)
    # Get user
    if "@" in user_ref:
        user = pd.get_user_by_email(user_ref)
    else:
        user = pd.get_user_by_id(user_ref)
    if not user:
        print(f"User not found: {user_ref}")
        return
    user_id = user['id']
    incidents = pd.list_user_incidents(user_id)
    if not incidents:
        print("No incidents assigned to user.")
        return
    for inc in incidents:
        inc_id = inc['id']
        inc_title = inc.get('title', '')
        inc_status = inc.get('status', '')
        inc_severity = inc.get('severity', None)
        if inc_status != 'resolved' and (not severity or inc_severity == severity):
            try:
                pd.resolve_incident(inc_id)
                print(f"Resolved incident: {inc_id} ({inc_title})")
            except Exception as e:
                print(f"Failed to resolve {inc_id}: {e}")
def main():
    import argparse
    parser = argparse.ArgumentParser(description="Acknowledge or resolve PagerDuty alerts for a user.")
    parser.add_argument('--action', choices=['ack', 'resolve'], required=True, help='Action to perform: ack (auto-acknowledge incidents), resolve (resolve incidents).')
    parser.add_argument('--user', required=True, help='User email or PagerDuty User ID.')
    parser.add_argument('--severity', help='Resolve only incidents of this severity (for resolve action).')
    parser.add_argument('--interval', type=int, default=10, help='Polling interval in seconds for ack action (default: 10).')
    args = parser.parse_args()
    if args.action == 'ack':
        acknowledge_incidents_loop(args.user, args.interval)
    elif args.action == 'resolve':
        resolve_incidents(args.user, args.severity)

if __name__ == "__main__":
    main()
