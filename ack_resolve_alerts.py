"""
PagerDuty Incident Auto-Acknowledge/Resolve Tool
==================================================
Standalone utility for automatically acknowledging or resolving incidents.

Two modes:
  1. --action ack    : Continuously monitors and auto-acknowledges triggered incidents
  2. --action resolve: One-time batch resolution of incidents (with optional severity filter)

Usage:
  python ack_resolve_alerts.py --action ack --user deepak.tr@sprinklr.com --interval 10
  python ack_resolve_alerts.py --action resolve --user deepak.tr@sprinklr.com --severity critical
"""

import sys
import os
import yaml
from pd_api import PagerDutyAPI

def load_config():
    """Load PagerDuty API token from config.yaml or environment variable."""
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
    """
    Continuously monitor and auto-acknowledge triggered incidents for a user.
    
    Process:
      1. Fetch all triggered/acknowledged incidents for user
      2. Auto-acknowledge any "triggered" incidents (prevents escalation)
      3. Track already-acknowledged incidents to avoid duplicates
      4. Sleep for poll_interval seconds
      5. Repeat indefinitely
    
    Args:
        user_ref: User email or ID to monitor
        poll_interval: Seconds between poll attempts (default: 10)
    """
    import time
    pd_token = load_config()
    pd = PagerDutyAPI(pd_token)
    
    # Resolve user reference (email or ID)
    if "@" in user_ref:
        user = pd.get_user_by_email(user_ref)
    else:
        user = pd.get_user_by_id(user_ref)
    if not user:
        print(f"User not found: {user_ref}")
        return
    
    user_id = user['id']
    print(f"Monitoring incidents for user: {user.get('name')} ({user.get('email')})")
    already_ack = set()  # Track acknowledged incidents to prevent duplicate acknowledgments
    
    # Continuous monitoring loop
    while True:
        incidents = pd.list_user_incidents(user_id)
        for inc in incidents:
            inc_id = inc['id']
            inc_title = inc.get('title', '')
            inc_status = inc.get('status', '')
            
            # Only acknowledge "triggered" incidents (not already acknowledged)
            if inc_status == 'triggered' and inc_id not in already_ack:
                try:
                    pd.acknowledge_incident(inc_id)
                    print(f"Acknowledged incident: {inc_id} ({inc_title})")
                    already_ack.add(inc_id)
                except Exception as e:
                    print(f"Failed to acknowledge {inc_id}: {e}")
        
        time.sleep(poll_interval)

def resolve_incidents(user_ref, severity=None):
    """
    One-time batch resolution of incidents for a user.
    
    Process:
      1. Fetch all triggered/acknowledged incidents for user
      2. Filter by severity if specified (--severity flag)
      3. Resolve each incident
      4. Exit
    
    Args:
        user_ref: User email or ID
        severity: Optional severity filter (critical, high, medium, low)
    """
    pd_token = load_config()
    pd = PagerDutyAPI(pd_token)
    
    # Resolve user reference (email or ID)
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
    
    # Resolve incidents
    for inc in incidents:
        inc_id = inc['id']
        inc_title = inc.get('title', '')
        inc_status = inc.get('status', '')
        inc_severity = inc.get('severity', None)
        
        # Only resolve if not already resolved AND matches severity filter
        if inc_status != 'resolved' and (not severity or inc_severity == severity):
            try:
                pd.resolve_incident(inc_id)
                print(f"Resolved incident: {inc_id} ({inc_title})")
            except Exception as e:
                print(f"Failed to resolve {inc_id}: {e}")

def main():
    """Parse arguments and execute appropriate action."""
    import argparse
    parser = argparse.ArgumentParser(description="Acknowledge or resolve PagerDuty alerts for a user.")
    parser.add_argument('--action', choices=['ack', 'resolve'], required=True,
                        help='Action to perform: ack (auto-acknowledge incidents), resolve (resolve incidents).')
    parser.add_argument('--user', required=True,
                        help='User email or PagerDuty User ID.')
    parser.add_argument('--severity',
                        help='Resolve only incidents of this severity (for resolve action).')
    parser.add_argument('--interval', type=int, default=10,
                        help='Polling interval in seconds for ack action (default: 10).')
    args = parser.parse_args()
    
    if args.action == 'ack':
        acknowledge_incidents_loop(args.user, args.interval)
    elif args.action == 'resolve':
        resolve_incidents(args.user, args.severity)


if __name__ == '__main__':
    main()


