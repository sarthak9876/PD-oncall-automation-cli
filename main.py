"""
PagerDuty CLI Automation Tool
==============================
A comprehensive command-line interface for managing PagerDuty users, escalation policies, and incidents.

Supported Actions:
  1. get-info   - Display detailed information about a user (teams, on-calls, incidents)
  2. add        - Create new user or configure existing user with policies/schedules/teams
  3. remove     - Safe user deletion with incident reassignment and schedule override
"""

import os
import sys
import argparse
import yaml
from pd_api import PagerDutyAPI

def load_config(token_arg=None, use_env=True):
    """
    Load PagerDuty API token from multiple sources in priority order:
    1. Command-line argument (--pagerduty-api-token)
    2. Environment variable (PAGERDUTY_API_TOKEN)
    3. Config file (config.yaml)
    """
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
    """
    Retrieve a PagerDuty user by email or user ID.
    - If user_ref contains '@', treats it as email
    - Otherwise, treats it as a user ID
    """
    if not user_ref:
        return None
    if "@" in user_ref:
        return pd.get_user_by_email(user_ref)
    else:
        return pd.get_user_by_id(user_ref)

def get_policy_ids(args, config, pd):
    """
    Collect escalation policy IDs from multiple sources in priority order:
    1. Explicitly provided policies (--policies, --policy)
    2. Service name (--service) - resolves to its escalation policy
    3. Default policy from config.yaml (default_policy_id)
    """
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
    """
    Display all teams the user is assigned to, with team IDs.
    """
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

# ============================================================================
# COMMENTED OUT: Alternative escalation policy display functions
# These were experimental approaches to display escalation policies.
# Currently using simpler on-call status display instead.
# ============================================================================

# def print_user_escalation_policies_via_targets(pd, user):
#     """Display escalation policies where user is a target (direct or via schedule)."""
#     user_id = user['id']
#     policies = pd.list_escalation_policies()
#     found = False
#     print("\nEscalation Policies where user is a target (direct or via schedule):")
#     for pol in policies:
#         pol_with_targets = pd.get_escalation_policy_with_targets(pol['id'])
#         summary = pol_with_targets['summary']
#         for target in pol_with_targets.get("targets", []):
#             if target['type'] == 'user_reference' and target['id'] == user_id:
#                 print(f"  - {summary} (ID: {pol_with_targets['id']}) [direct user]")
#                 found = True
#             if target['type'] == 'schedule_reference':
#                 schedule_users = pd.get_schedule_users(target['id'])
#                 if user_id in schedule_users:
#                     print(f"  - {summary} (ID: {pol_with_targets['id']}) [via schedule]")
#                     found = True
#     if not found:
#         print("  (User is not a target in any escalation policy.)")

# def print_user_escalation_policies_full(pd, user):
#     """Display escalation policies where user is assigned (direct or via schedule)."""
#     user_id = user['id']
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
#                     sched_id = target["id"]
#                     schedule_users = pd.get_schedule_users(sched_id)
#                     if user_id in schedule_users:
#                         print(f"  - {pol['summary']} (ID: {pol['id']}), Level: {rule_no}, Schedule: {target.get('summary', sched_id)} (ID: {sched_id}) [assigned via schedule]")
#                         found = True
#     if not found:
#         print("  (User is not assigned in any escalation policy.)")

# ============================================================================

def print_user_info(pd, user):
    """
    Display comprehensive user information including:
    - Basic details (name, email, ID, role)
    - Team memberships
    - Current on-call status in escalation policies/schedules
    - Assigned incidents (triggered/acknowledged status)
    """
    print("\nUser Details:")
    print(f"  Name     : {user.get('name')}")
    print(f"  Email    : {user.get('email')}")
    print(f"  ID       : {user.get('id')}")
    print(f"  Base Role: {user.get('role', 'N/A')}")
    print_user_teams_and_roles(pd, user)
    
    # Display current on-call status
    print("Current oncall Escalation Policies/Schedules of the user:")
    oncalls = pd.get_user_oncalls(user['id'])
    if oncalls:
        for oncall in oncalls:
            ep = oncall['escalation_policy']
            schedule = oncall.get('schedule')
            schedule_summary = schedule['summary'] if schedule and 'summary' in schedule else "(No schedule info)"
            print(f"✅ - {ep['summary']} - {schedule_summary}")
    else:
        print("❌ The user is currently not on-call in any escalation policy/schedule")
    
    # Display assigned incidents
    print("\nCurrent assigned incidents:")
    incidents = pd.list_user_incidents(user['id'])
    if incidents:
        for inc in incidents:
            print(f"  - [{inc['status']}] {inc['title']} ({inc['id']})")
    else:
        print("  (No incidents assigned.)")

def main():
    """
    Main CLI entry point. Parses arguments and delegates to appropriate action handler.
    """
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
    parser.add_argument('--level', type=int,
                        help='Escalation rule index/level in the policy (0=first, 1=second, etc). Optional.')
    parser.add_argument('--schedule',
                        help='Schedule name to add the user to (optional). If provided, user is added to the schedule instead of escalation policy.')
    parser.add_argument('--start-time',
                        help='Start time for schedule assignment (ISO 8601 format, e.g., "2025-11-27T06:00:00+05:30"). Only used with --schedule.')
    parser.add_argument('--end-time',
                        help='End time for schedule assignment (ISO 8601 format, e.g., "2025-11-27T15:00:00+05:30"). Only used with --schedule.')
    parser.add_argument('--team',
                        help='Team name or ID to add the user to (optional).')
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

    # ========================================================================
    # ACTION: GET-INFO
    # Purpose: Display user details, team memberships, on-call status, incidents
    # ========================================================================
    if args.action == "get-info":
        for user_ref in user_list:
            user = get_user(pd, user_ref)
            if not user:
                print(f"User not found: {user_ref}")
                continue
            print_user_info(pd, user)
        sys.exit(0)

    # ========================================================================
    # ACTION: ADD
    # Purpose: Create new user OR configure existing user with:
    #   - Team membership (--team)
    #   - Schedule assignment (--schedule) with optional time window
    #   - Escalation policy assignment (--policy) at specified level (--level)
    # Note: Schedule and Policy assignments are mutually exclusive (XOR)
    # ========================================================================
    if args.action == "add":
        for idx, user_ref in enumerate(user_list):
            # Validate email domain
            if not user_ref or "@sprinklr.com" not in user_ref:
                print(f"User email required and must be @sprinklr.com: {user_ref}")
                continue
            
            # Get user if already exists
            user = get_user(pd, user_ref)
            user_name = args.user_name if isinstance(args.user_name, str) else (args.user_name[idx] if args.user_name and len(args.user_name) > idx else None)
            user_role = args.user_role if isinstance(args.user_role, str) else (args.user_role[idx] if args.user_role and len(args.user_role) > idx else None)
            
            # Create user if doesn't exist
            if not user:
                if not user_name or not user_role:
                    print(f"For new user {user_ref}, supply --user-name and --user-role")
                    continue
                user = pd.create_user(user_ref, user_name, user_role)
                print("✅ User created:", user['summary'])
                print(f"   Username: {user['name']}")
                print(f"   User ID: {user['id']}")
            else:
                print("✅ User found:", user['summary'])
                print(f"   Username: {user['name']}")
                print(f"   User ID: {user['id']}")
            
            # Step 1: Add user to team (optional)
            if args.team:
                print(f"\n👥 Adding user to team: {args.team}")
                team = pd.get_team_by_name(args.team)
                if not team:
                    team = pd.get_team_by_id(args.team)
                
                if not team:
                    print(f"❌ Team '{args.team}' not found (checked by name and ID).")
                    print("   Tip: Use --team with team name or team ID (e.g., PI4L6P9)")
                else:
                    team_id = team['id']
                    print(f"   Found team: {team['summary']} (ID: {team_id})")
                    did_add = pd.add_user_to_team(team_id, user['id'])
                    if did_add:
                        print(f"✅ Added user {user_ref} to team {team['summary']} (ID: {team_id}).")
                    else:
                        print(f"⚠️  Could not add user {user_ref} to team {team['summary']}.")
                        print("   Possible reasons: User already in team, team access issues, or API limitations.")
            
            # Step 2: Add to SCHEDULE (if specified) - optional
            if args.schedule:
                print(f"\n📅 Adding user to schedule: {args.schedule}")
                schedule = pd.get_schedule_by_name(args.schedule)
                if not schedule:
                    print(f"❌ Schedule '{args.schedule}' not found.")
                    continue
                
                schedule_id = schedule['id']
                did_add = pd.add_user_to_schedule_layer(schedule_id, user['id'], args.start_time, args.end_time)
                if did_add:
                    time_window = ""
                    if args.start_time and args.end_time:
                        time_window = f" from {args.start_time} to {args.end_time}"
                    print(f"✅ Added user {user_ref} to schedule {args.schedule}{time_window}.")
                else:
                    print(f"❌ Failed to add user to schedule {args.schedule}.")
            
            # Step 3: Add to ESCALATION POLICY (if schedule not specified) - optional
            # Note: Schedule and Policy assignments are mutually exclusive
            elif args.policy or args.policies or args.service or "default_policy_id" in config:
                try:
                    policy_ids = get_policy_ids(args, config, pd)
                    for pid in policy_ids:
                        policy = pd.get_escalation_policy(pid)
                        
                        # Interactive level selection if not specified
                        if args.level is None:
                            print(f"\n📋 Escalation rules in policy {pid}:")
                            rules = pd.list_escalation_rules(pid)
                            for rule in rules:
                                print(f"  Level {rule['index']}: {rule['id']} (Delay: {rule['escalation_delay_in_minutes']}min) - Targets: {len(rule['targets'])}")
                            
                            level_input = input(f"Enter level to add user to (0-{len(rules)-1}) [default: {len(rules)-1}]: ").strip()
                            rule_index = int(level_input) if level_input else len(rules) - 1
                        else:
                            rule_index = args.level
                        
                        did_add = pd.add_user_to_policy(policy, user['id'], user.get('role','user'), rule_index=rule_index)
                        if did_add:
                            pd.update_escalation_policy(pid, policy)
                            print(f"✅ Added user {user_ref} to escalation policy {pid} at level {rule_index}.")
                        else:
                            print(f"⚠️  User {user_ref} already present in escalation policy {pid} at level {rule_index}.")
                except SystemExit:
                    # get_policy_ids calls sys.exit(1) if no policy found, skip instead
                    print(f"⚠️  No policy specified for user {user_ref}. User created without policy assignment.")
            else:
                print(f"✅ User {user_ref} created successfully. No policy or schedule specified.")

    # ========================================================================
    # ACTION: REMOVE
    # Purpose: Safely delete a user from PagerDuty with multi-stage cleanup:
    #   1. Check current on-call status
    #   2. Remove from escalation policies
    #   3. Reassign incidents to escalation policy (round-robin distribution)
    #   4. Override user in all schedules
    #   5. Delete user
    # This ensures no orphaned incidents or on-call assignments remain
    # ========================================================================
    if args.action == "remove":
        for user_ref in user_list:
            user = get_user(pd, user_ref)
            if not user:
                print(f"User not found: {user_ref}")
                continue

            # Stage 1: Show current on-call status
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

            # Stage 2: Remove from escalation policies
            print(f"\nRemoving user {user_ref} from escalation policies and schedules...")
            removed_from_any = False
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

            # Stage 3: Reassign incidents to escalation policy (round-robin)
            print(f"\nChecking for active incidents for {user_ref}:")
            incidents = pd.list_user_incidents(user['id'])
            if incidents:
                print(f"Re-assigning the incidents before deletion of user {user_ref}. Please wait while reassignment is taking place...")
                for inc in incidents:
                    ep_id = inc.get('escalation_policy', {}).get('id')
                    if ep_id:
                        try:
                            # Reassign to policy (not user) for automatic round-robin distribution
                            pd.reassign_incident_to_policy(inc['id'], ep_id)
                            print(f"  - Reassigned incident {inc['id']} ({inc['title']}) to escalation policy for round-robin distribution")
                        except Exception as e:
                            print(f"  - Failed to reassign incident {inc['id']}: {str(e)}")
                print("Incidents re-assigned successfully.")
            else:
                print(f"No active incidents found for the user {user_ref}.")

            # Stage 4 & 5: Delete user (with schedule/policy overrides handled in pd_api.delete_user)
            print(f"\nProceeding with user deletion for {user_ref}...")
            pd.delete_user(user['id'])
            print(f"Successfully deleted user {user.get('name')} ({user.get('email')})")

if __name__ == "__main__":
    main()




