import os
import sys
import argparse
import yaml
from pd_api import PagerDutyAPI

def load_config(token_arg=None, use_env=True):
    config = {}
    if os.path.exists("config.yaml"):
        with open("config.yaml", "r") as f:
            config = yaml.safe_load(f)
    pd_token = None
    if token_arg:
        pd_token = token_arg
    elif use_env:
        pd_token = os.environ.get("PAGERDUTY_API_TOKEN")
    if not pd_token:
        pd_token = config.get("pagerduty_api_token")
    if not pd_token:
        print("PagerDuty API token missing (argument, env variable, or config.yaml)")
        sys.exit(1)
    return pd_token, config

def get_user(pd, user_ref):
    if not user_ref:
        return None
    if "@" in user_ref:
        return pd.get_user_by_email(user_ref)
    else:
        return pd.get_user_by_id(user_ref)

def get_policy_ids(args, config, pd):
    policy_ids = set()
    if args.policies:
        for pid in args.policies:
            policy_ids.add(pid)
    if args.policy:
        policy_ids.add(args.policy)
    if args.service:
        pid = pd.get_policy_id_from_service(args.service)
        if pid:
            policy_ids.add(pid)
    if not policy_ids and "default_policy_id" in config:
        policy_ids.add(config["default_policy_id"])
    if not policy_ids:
        print("Policy (or service) not specified and no default in config.")
        sys.exit(1)
    return list(policy_ids)

def print_user_teams_and_roles(pd, user):
    teams = user.get("teams", [])
    if not teams:
        print("  (User is not in any teams.)")
        return
    team_objs = pd.list_teams()
    team_objs_map = {t['id']: t for t in team_objs}
    print("Teams:")
    for team_ref in teams:
        tid = team_ref.get("id")
        tname = team_objs_map.get(tid, {}).get('summary', tid)
        print(f"  - {tname} (ID: {tid})")
    print()

# def print_user_escalation_policies_via_targets(pd, user):
#     user_id = user['id']
#     policies = pd.list_escalation_policies()
#     found = False
#     print("\nEscalation Policies where user is a target (direct or via schedule):")
#     for pol in policies:
#         # Fetch policy with targets included
#         pol_with_targets = pd.get_escalation_policy_with_targets(pol['id'])
#         summary = pol_with_targets['summary']
#         # Check direct user targets
#         for target in pol_with_targets.get("targets", []):
#             if target['type'] == 'user_reference' and target['id'] == user_id:
#                 print(f"  - {summary} (ID: {pol_with_targets['id']}) [direct user]")
#                 found = True
#             # Check schedule targets
#             if target['type'] == 'schedule_reference':
#                 schedule_users = pd.get_schedule_users(target['id'])
#                 if user_id in schedule_users:
#                     print(f"  - {summary} (ID: {pol_with_targets['id']}) [via schedule]")
#                     found = True
#     if not found:
#         print("  (User is not a target in any escalation policy.)")

# def print_user_escalation_policies_full(pd, user):
#     user_id = user['id']
#     user_email = user.get('email', '').lower()
#     all_policies = pd.list_escalation_policies()
#     found = False
#     print("\nEscalation Policies where user is assigned (direct or via schedule):")
#     for pol in all_policies:
#         pol_with_targets = pd.get_escalation_policy_with_targets(pol['id'])
#         for rule_no, rule in enumerate(pol_with_targets.get("escalation_rules", []), 1):
#             for target in rule.get("targets", []):
#                 if target["type"] == "user" and target["id"] == user_id:
#                     print(f"  - {pol['summary']} (ID: {pol['id']}), Level: {rule_no} [direct assignment]")
#                     found = True
#                 elif target["type"] == "schedule":
#                     # Optionally, check if user is assigned to this schedule
#                     sched_id = target["id"]
#                     schedule_users = pd.get_schedule_users(sched_id)
#                     if user_id in schedule_users:
#                         print(f"  - {pol['summary']} (ID: {pol['id']}), Level: {rule_no}, Schedule: {target.get('summary', sched_id)} (ID: {sched_id}) [assigned via schedule]")
#                         found = True
#     if not found:
#         print("  (User is not assigned in any escalation policy.)")

def print_user_info(pd, user):
    print("\nUser Details:")
    print(f"  Name     : {user.get('name')}")
    print(f"  Email    : {user.get('email')}")
    print(f"  ID       : {user.get('id')}")
    print(f"  Base Role: {user.get('role', 'N/A')}")
    print_user_teams_and_roles(pd, user)
    # print_user_escalation_policies_via_targets(pd, user)
    
    # Display oncall information
    print("\nCurrent oncall Escalation Policies/Schedules of the user:")
    oncalls = pd.get_user_oncalls(user['id'])
    if oncalls:
        for oncall in oncalls:
            ep = oncall['escalation_policy']
            schedule = oncall.get('schedule')
            schedule_summary = schedule['summary'] if schedule and 'summary' in schedule else "(No schedule info)"
            print(f"✅ - {ep['summary']} - {schedule_summary}")
    else:
        print("❌ The user is currently not on-call in any escalation policy/schedule")
    
    print("\nCurrent assigned incidents:")
    incidents = pd.list_user_incidents(user['id'])
    if incidents:
        for inc in incidents:
            print(f"  - [{inc['status']}] {inc['title']} ({inc['id']})")
    else:
        print("  (No incidents assigned.)")

def main():
    parser = argparse.ArgumentParser(
        description="PagerDuty CLI: add/remove/get-info on escalation policies",
        epilog="Example usage:\n  python main.py --action get-info --user user@example.com\n  python main.py --action add --user user@sprinklr.com --user-name 'Full Name' --user-role responder --policy POLICY_ID --pagerduty-api-token TOKEN"
    )
    parser.add_argument('--action', choices=["get-info", "add", "remove"], required=True,
                        help='Action to perform: get-info (show user info), add (add user to policy), remove (delete user and reassign incidents).')
    parser.add_argument('--user', nargs='+', required=True,
                        help='User email(s) or PagerDuty User ID(s). Accepts one or more values. Required for all actions.')
    parser.add_argument('--user-name',
                        help='Full name of the user (required when adding a new user).')
    parser.add_argument('--user-role',
                        help='Role for the user (e.g. manager, responder, user, etc). Required when adding a new user.')
    parser.add_argument('--policy',
                        help='Escalation Policy ID to operate on. Optional if --service or --policies is provided.')
    parser.add_argument('--policies', nargs='+',
                        help='Space-separated list of escalation policy IDs to operate on.')
    parser.add_argument('--service',
                        help='Service name to resolve escalation policy automatically.')
    parser.add_argument('--pagerduty-api-token',
                        help='PagerDuty API token. Recommended to use environment variable for safety.')
    parser.add_argument('--no-env', action='store_true',
                        help='Do not fetch token from environment variable. Use only argument or config.yaml.')
    args = parser.parse_args()

    pd_token, config = load_config(token_arg=args.pagerduty_api_token, use_env=not args.no_env)
    pd = PagerDutyAPI(pd_token)

    if not args.user:
        print("--user is required (email or user id)")
        sys.exit(1)
    user_list = args.user if isinstance(args.user, list) else [args.user]

    # GET-INFO
    if args.action == "get-info":
        for user_ref in user_list:
            user = get_user(pd, user_ref)
            if not user:
                print(f"User not found: {user_ref}")
                continue
            print_user_info(pd, user)
        sys.exit(0)

    # ADD
    if args.action == "add":
        for idx, user_ref in enumerate(user_list):
            if not user_ref or "@sprinklr.com" not in user_ref:
                print(f"User email required and must be @sprinklr.com: {user_ref}")
                continue
            user = get_user(pd, user_ref)
            user_name = args.user_name if isinstance(args.user_name, str) else (args.user_name[idx] if args.user_name and len(args.user_name) > idx else None)
            user_role = args.user_role if isinstance(args.user_role, str) else (args.user_role[idx] if args.user_role and len(args.user_role) > idx else None)
            if not user:
                if not user_name or not user_role:
                    print(f"For new user {user_ref}, supply --user-name and --user-role")
                    continue
                user = pd.create_user(user_ref, user_name, user_role)
                print("User created:", user['summary'])
            else:
                print("User found:", user['summary'])
            policy_ids = get_policy_ids(args, config, pd)
            for pid in policy_ids:
                policy = pd.get_escalation_policy(pid)
                as_first = user['role'].startswith('user') or user['role'].startswith('limited')
                did_add = pd.add_user_to_policy(policy, user['id'], user.get('role','user'), as_first=as_first)
                if did_add:
                    pd.update_escalation_policy(pid, policy)
                    print(f"Added user {user_ref} to policy {pid} at {'top' if as_first else 'bottom'} of on-call.")
                else:
                    print(f"User {user_ref} already present in policy {pid}.")

    # REMOVE
    if args.action == "remove":
        for user_ref in user_list:
            user = get_user(pd, user_ref)
            if not user:
                print(f"User not found: {user_ref}")
                continue

            # First show current oncall status
            print(f"\nChecking current oncall status for {user_ref}:")
            oncalls = pd.get_user_oncalls(user['id'])
            if oncalls:
                print(f"User {user_ref} is currently on-call in following Escalation policies/schedules:")
                for oncall in oncalls:
                    ep = oncall['escalation_policy']
                    schedule = oncall.get('schedule')
                    schedule_summary = schedule['summary'] if schedule and 'summary' in schedule else "(No schedule info)"
                    print(f"✅ - {ep['summary']} - {schedule_summary}")
            else:
                print(f"User {user_ref} is not currently on-call in any Escalation Policy.")

            # Remove user from all escalation policies and schedules
            print(f"\nRemoving user {user_ref} from escalation policies and schedules...")
            removed_from_any = False
            # Collect all unique escalation policy IDs
            policy_ids = set()
            for oncall in oncalls:
                ep = oncall.get('escalation_policy')
                if ep and 'id' in ep:
                    policy_ids.add(ep['id'])
            for pid in policy_ids:
                policy = pd.get_escalation_policy(pid)
                changed = pd.remove_user_from_policy(policy, user['id'])
                if changed:
                    pd.update_escalation_policy(pid, policy)
                    print(f"Removed user {user_ref} from escalation policy: {policy.get('summary', pid)} (ID: {pid})")
                    removed_from_any = True
                else:
                    print(f"User {user_ref} was not present in escalation policy: {policy.get('summary', pid)} (ID: {pid})")
            if not removed_from_any:
                print(f"User {user_ref} was not present in any escalation policy.")

            # Check for active incidents
            print(f"\nChecking for active incidents for {user_ref}:")
            incidents = pd.list_user_incidents(user['id'])
            if incidents:
                print(f"Re-assigning the incidents before deletion of user {user_ref}. Please wait while reassignment is taking place...")
                # For each incident, find another user in the same policy to reassign to
                for inc in incidents:
                    ep_id = inc.get('escalation_policy', {}).get('id')
                    if ep_id:
                        policy_users = pd.get_policy_users(ep_id)
                        # Find another user that's not the one being removed
                        alternative_users = [u for u in policy_users if u != user['id']]
                        if alternative_users:
                            pd.reassign_incident(inc['id'], alternative_users[0])
                            print(f"  - Reassigned incident {inc['id']} ({inc['title']})")
                print("Incidents re-assigned successfully.")
            else:
                print(f"No active incidents found for the user {user_ref}.")

            print(f"\nProceeding with user deletion for {user_ref}...")
            pd.delete_user(user['id'])
            print(f"Successfully deleted user {user.get('name')} ({user.get('email')})")

if __name__ == "__main__":
    main()




