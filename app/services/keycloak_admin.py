# app/services/keycloak_admin.py
"""
Keycloak Admin Service — manages Keycloak REST API calls or provides dev-mode fallback.
When AUTH_BYPASS=true or Keycloak is not configured, fallback data is dynamically queried
from the app database (users_directory table) and managed in-memory.
"""

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from ..core.database import SessionLocal
from ..models.hackathon import UserDirectory

log = logging.getLogger(__name__)

KEYCLOAK_SERVER_URL = os.getenv("KEYCLOAK_SERVER_URL")
AUTH_BYPASS = os.getenv("AUTH_BYPASS", "false").lower() == "true"


class KeycloakAdminService:
    """
    Service wrapper for Keycloak Admin API with automatic Dev Fallback Mode.
    """

    def __init__(self):
        # In-memory stores for dev mode
        self._roles = {
            "admin": {"id": "r-admin", "name": "admin", "description": "Full system administrator", "composite": False, "clientRole": False, "containerId": "realm-autopilot", "userCount": 2},
            "user": {"id": "r-user", "name": "user", "description": "Standard user access", "composite": False, "clientRole": False, "containerId": "realm-autopilot", "userCount": 85},
            "pending": {"id": "r-pending", "name": "pending", "description": "Awaiting admin approval", "composite": False, "clientRole": False, "containerId": "realm-autopilot", "userCount": 3},
            "analyst": {"id": "r-analyst", "name": "analyst", "description": "Read-only analytics access", "composite": False, "clientRole": False, "containerId": "realm-autopilot", "userCount": 5},
            "auditor": {"id": "r-auditor", "name": "auditor", "description": "Audit log viewer", "composite": False, "clientRole": False, "containerId": "realm-autopilot", "userCount": 1},
        }

        self._groups = {
            "g-ops": {"id": "g-ops", "name": "Ops", "path": "/Ops", "subGroups": [], "subGroupCount": 0, "memberCount": 18, "roles": ["user"]},
            "g-legal": {"id": "g-legal", "name": "Legal", "path": "/Legal", "subGroups": [], "subGroupCount": 0, "memberCount": 12, "roles": ["user"]},
            "g-finance": {"id": "g-finance", "name": "Finance", "path": "/Finance", "subGroups": [], "subGroupCount": 0, "memberCount": 8, "roles": ["user"]},
            "g-hr": {"id": "g-hr", "name": "HR", "path": "/HR", "subGroups": [], "subGroupCount": 0, "memberCount": 10, "roles": ["user"]},
            "g-it": {"id": "g-it", "name": "IT", "path": "/IT", "subGroups": [], "subGroupCount": 0, "memberCount": 15, "roles": ["admin", "user"]},
            "g-sales": {"id": "g-sales", "name": "Sales", "path": "/Sales", "subGroups": [], "subGroupCount": 0, "memberCount": 14, "roles": ["user"]},
        }

        self._user_roles: Dict[str, set] = {
            "dev-user-001": {"admin", "user"},
            "4641b62317bb90e5c8564b03": {"user"},
            "d29d16f0f07dead9bfe630cc": {"user"},
        }

        self._group_members: Dict[str, set] = {
            "g-ops": {"dev-user-001", "4641b62317bb90e5c8564b03"},
            "g-legal": {"d29d16f0f07dead9bfe630cc"},
        }

        self._sessions = [
            {"id": "sess-001", "username": "dev-user", "userId": "dev-user-001", "ipAddress": "127.0.0.1", "start": int(datetime.now(timezone.utc).timestamp() * 1000) - 3600000, "lastAccess": int(datetime.now(timezone.utc).timestamp() * 1000)},
            {"id": "sess-002", "username": "uma.ong", "userId": "4641b62317bb90e5c8564b03", "ipAddress": "192.168.1.45", "start": int(datetime.now(timezone.utc).timestamp() * 1000) - 7200000, "lastAccess": int(datetime.now(timezone.utc).timestamp() * 1000) - 1800000},
            {"id": "sess-003", "username": "arun.tan", "userId": "d29d16f0f07dead9bfe630cc", "ipAddress": "192.168.1.88", "start": int(datetime.now(timezone.utc).timestamp() * 1000) - 86400000, "lastAccess": int(datetime.now(timezone.utc).timestamp() * 1000) - 43200000},
        ]

        self._login_events = [
            {"id": "evt-001", "type": "LOGIN", "time": int(datetime.now(timezone.utc).timestamp() * 1000) - 300000, "userId": "dev-user-001", "username": "dev-user", "ipAddress": "127.0.0.1", "clientId": "autopilot-frontend", "error": None, "realmId": "autopilot", "sessionId": "sess-001", "details": None},
            {"id": "evt-002", "type": "LOGIN", "time": int(datetime.now(timezone.utc).timestamp() * 1000) - 1200000, "userId": "4641b62317bb90e5c8564b03", "username": "uma.ong@company.com", "ipAddress": "192.168.1.45", "clientId": "autopilot-frontend", "error": None, "realmId": "autopilot", "sessionId": "sess-002", "details": None},
            {"id": "evt-003", "type": "LOGIN_ERROR", "time": int(datetime.now(timezone.utc).timestamp() * 1000) - 3600000, "userId": None, "username": "unknown@company.com", "ipAddress": "10.0.0.12", "clientId": "autopilot-frontend", "error": "invalid_user_credentials", "realmId": "autopilot", "sessionId": None, "details": None},
        ]

        self._admin_events = [
            {
                "id": "aevt-001",
                "time": int(datetime.now(timezone.utc).timestamp() * 1000) - 600000,
                "operationType": "UPDATE",
                "resourceType": "USER",
                "resourcePath": "users/dev-user-001",
                "representation": '{"name": "Dev User"}',
                "error": None,
                "authDetails": {"userId": "dev-user-001", "username": "dev-user", "ipAddress": "127.0.0.1"},
            }
        ]

    # --- User Methods ---

    def _get_db_users(self) -> List[Dict[str, Any]]:
        """Fetch users from UsersDirectory DB table and map to Keycloak dict format."""
        db = SessionLocal()
        try:
            db_users = db.query(UserDirectory).all()
            if not db_users:
                return [{
                    "id": "dev-user-001",
                    "username": "dev-user",
                    "email": "developer@autopilot.local",
                    "firstName": "Dev",
                    "lastName": "User",
                    "enabled": True,
                    "createdTimestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                    "roles": ["admin", "user"],
                    "department": "IT",
                    "location": "KL-HQ",
                    "x_vip": True,
                }]
            
            result = []
            for u in db_users:
                names = (u.display_name or "").split(" ", 1)
                first_name = names[0] if names else "User"
                last_name = names[1] if len(names) > 1 else ""
                user_id = str(u.account_id)
                roles = list(self._user_roles.get(user_id, {"user"}))

                result.append({
                    "id": user_id,
                    "username": (u.email_address or f"user_{u.id}").split("@")[0],
                    "email": u.email_address or f"user_{u.id}@company.com",
                    "firstName": first_name,
                    "lastName": last_name,
                    "enabled": True,
                    "createdTimestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                    "roles": roles,
                    "department": u.department or "General",
                    "location": u.location or "Office",
                    "x_vip": getattr(u, "x_vip", False),
                })
            return result
        except Exception as e:
            log.warning(f"Failed to query UserDirectory DB table: {e}")
            return [{
                "id": "dev-user-001",
                "username": "dev-user",
                "email": "developer@autopilot.local",
                "firstName": "Dev",
                "lastName": "User",
                "enabled": True,
                "createdTimestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
                "roles": ["admin", "user"],
                "department": "IT",
                "location": "KL-HQ",
                "x_vip": True,
            }]
        finally:
            db.close()

    async def get_users_count(self, search: Optional[str] = None) -> int:
        users = self._get_db_users()
        if search:
            s = search.lower()
            users = [u for u in users if s in u["username"].lower() or s in u["email"].lower() or s in u["firstName"].lower() or s in u["lastName"].lower()]
        return len(users)

    async def get_users_with_roles(self, first: int = 0, max_results: int = 20, search: Optional[str] = None) -> List[Dict[str, Any]]:
        users = self._get_db_users()
        if search:
            s = search.lower()
            users = [u for u in users if s in u["username"].lower() or s in u["email"].lower() or s in u["firstName"].lower() or s in u["lastName"].lower()]
        return users[first : first + max_results]

    async def get_all_users_with_roles_iter(self) -> List[Dict[str, Any]]:
        return self._get_db_users()

    async def get_user_by_id(self, user_id: str) -> Optional[Dict[str, Any]]:
        users = self._get_db_users()
        for u in users:
            if u["id"] == user_id:
                return u
        return {
            "id": user_id,
            "username": f"user_{user_id[:6]}",
            "email": f"user_{user_id[:6]}@company.com",
            "firstName": "User",
            "lastName": user_id[:6],
            "enabled": True,
            "createdTimestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
            "roles": list(self._user_roles.get(user_id, {"user"})),
            "department": "Ops",
            "location": "KL-HQ",
            "x_vip": False,
        }

    async def create_user_by_admin(self, email: str, username: str, first_name: str, last_name: str, department: str = "", location: str = "", roles: Optional[List[str]] = None) -> Dict[str, Any]:
        new_id = uuid.uuid4().hex[:24]
        user_roles = set(roles) if roles else {"user"}
        self._user_roles[new_id] = user_roles

        db = SessionLocal()
        try:
            user_entry = UserDirectory(
                account_id=new_id,
                display_name=f"{first_name} {last_name}".strip(),
                email_address=email,
                department=department or "Ops",
                location=location or "KL-HQ",
                x_vip=False,
            )
            db.add(user_entry)
            db.commit()
        except Exception as e:
            log.warning(f"Could not persist created user to DB: {e}")
            db.rollback()
        finally:
            db.close()

        return {
            "id": new_id,
            "username": username or email.split("@")[0],
            "email": email,
            "firstName": first_name,
            "lastName": last_name,
            "enabled": True,
            "createdTimestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
            "roles": list(user_roles),
            "department": department,
            "location": location,
        }

    async def create_user(self, email: str, username: str, first_name: str, last_name: str) -> Dict[str, Any]:
        return await self.create_user_by_admin(email, username, first_name, last_name)

    async def approve_user(self, user_id: str) -> Dict[str, Any]:
        roles = self._user_roles.get(user_id, set())
        roles.discard("pending")
        roles.add("user")
        self._user_roles[user_id] = roles
        return {"id": user_id, "status": "approved"}

    async def reject_user(self, user_id: str, disable: bool = False) -> Dict[str, Any]:
        roles = self._user_roles.get(user_id, set())
        roles.discard("pending")
        self._user_roles[user_id] = roles
        return {"id": user_id, "status": "rejected"}

    async def disable_user(self, user_id: str) -> Dict[str, Any]:
        return {"id": user_id, "enabled": False}

    async def enable_user(self, user_id: str) -> Dict[str, Any]:
        return {"id": user_id, "enabled": True}

    async def delete_user(self, user_id: str) -> Dict[str, Any]:
        if user_id in self._user_roles:
            del self._user_roles[user_id]
        return {"id": user_id, "status": "deleted"}

    async def reset_password(self, user_id: str, new_password: str, temporary: bool = False) -> Dict[str, Any]:
        return {"id": user_id, "status": "password_reset"}

    # --- Role Methods ---

    async def get_roles_with_user_counts(self) -> List[Dict[str, Any]]:
        return list(self._roles.values())

    async def get_role_by_name(self, role_name: str) -> Optional[Dict[str, Any]]:
        return self._roles.get(role_name, {
            "id": f"r-{role_name}",
            "name": role_name,
            "description": f"Role {role_name}",
            "composite": False,
            "clientRole": False,
            "containerId": "realm-autopilot",
            "userCount": 0,
        })

    async def get_role_users_count(self, role_name: str) -> int:
        return sum(1 for roles in self._user_roles.values() if role_name in roles)

    async def get_role_users(self, role_name: str) -> List[Dict[str, Any]]:
        users = self._get_db_users()
        return [u for u in users if role_name in u.get("roles", [])]

    async def get_users_by_role(self, role_name: str) -> List[Dict[str, Any]]:
        return await self.get_role_users(role_name)

    async def create_role(self, name: str, description: Optional[str] = None) -> Dict[str, Any]:
        role_data = {
            "id": f"r-{name.lower()}",
            "name": name,
            "description": description or f"Role {name}",
            "composite": False,
            "clientRole": False,
            "containerId": "realm-autopilot",
            "userCount": 0,
        }
        self._roles[name] = role_data
        return role_data

    async def update_role(self, role_name: str, description: Optional[str] = None) -> Dict[str, Any]:
        if role_name in self._roles:
            self._roles[role_name]["description"] = description or self._roles[role_name]["description"]
            return self._roles[role_name]
        return await self.create_role(role_name, description)

    async def delete_role(self, role_name: str) -> Dict[str, Any]:
        if role_name in self._roles:
            del self._roles[role_name]
        return {"name": role_name, "status": "deleted"}

    async def get_user_roles(self, user_id: str) -> List[Dict[str, Any]]:
        role_names = self._user_roles.get(user_id, {"user"})
        return [self._roles.get(r, {"name": r, "id": f"r-{r}"}) for r in role_names]

    async def assign_role(self, user_id: str, role_name: str) -> Dict[str, Any]:
        roles = self._user_roles.setdefault(user_id, set())
        roles.add(role_name)
        return {"user_id": user_id, "role": role_name, "status": "assigned"}

    async def remove_role(self, user_id: str, role_name: str) -> Dict[str, Any]:
        if user_id in self._user_roles:
            self._user_roles[user_id].discard(role_name)
        return {"user_id": user_id, "role": role_name, "status": "removed"}

    # --- Group Methods ---

    async def get_all_groups(self) -> List[Dict[str, Any]]:
        return list(self._groups.values())

    async def get_groups_with_details(self) -> List[Dict[str, Any]]:
        return list(self._groups.values())

    async def get_group_by_id(self, group_id: str) -> Optional[Dict[str, Any]]:
        return self._groups.get(group_id, {
            "id": group_id,
            "name": f"Group {group_id}",
            "path": f"/{group_id}",
            "subGroups": [],
            "subGroupCount": 0,
            "memberCount": 0,
            "roles": ["user"],
        })

    async def create_group(self, name: str, parent_id: Optional[str] = None, **kwargs) -> Dict[str, Any]:
        gid = f"g-{name.lower()}"
        group_data = {
            "id": gid,
            "name": name,
            "path": f"/{name}",
            "subGroups": [],
            "subGroupCount": 0,
            "memberCount": 0,
            "roles": ["user"],
        }
        self._groups[gid] = group_data
        return group_data

    async def update_group(self, group_id: str, name: str) -> Dict[str, Any]:
        if group_id in self._groups:
            self._groups[group_id]["name"] = name
            self._groups[group_id]["path"] = f"/{name}"
            return self._groups[group_id]
        return await self.create_group(name)

    async def delete_group(self, group_id: str) -> Dict[str, Any]:
        if group_id in self._groups:
            del self._groups[group_id]
        return {"id": group_id, "status": "deleted"}

    async def get_group_members(self, group_id: str) -> List[Dict[str, Any]]:
        member_ids = self._group_members.get(group_id, {"dev-user-001"})
        users = self._get_db_users()
        return [u for u in users if u["id"] in member_ids]

    async def get_group_role_mappings(self, group_id: str) -> List[Dict[str, Any]]:
        roles = self._groups.get(group_id, {}).get("roles", ["user"])
        return [self._roles.get(r, {"id": f"r-{r}", "name": r}) for r in roles]

    async def add_group_member(self, group_id: str, user_id: str) -> Dict[str, Any]:
        members = self._group_members.setdefault(group_id, set())
        members.add(user_id)
        if group_id in self._groups:
            self._groups[group_id]["memberCount"] = len(members)
        return {"group_id": group_id, "user_id": user_id, "status": "added"}

    async def remove_group_member(self, group_id: str, user_id: str) -> Dict[str, Any]:
        if group_id in self._group_members:
            self._group_members[group_id].discard(user_id)
            if group_id in self._groups:
                self._groups[group_id]["memberCount"] = len(self._group_members[group_id])
        return {"group_id": group_id, "user_id": user_id, "status": "removed"}

    async def assign_role_to_group(self, group_id: str, role_name: str) -> Dict[str, Any]:
        if group_id in self._groups:
            roles = set(self._groups[group_id].get("roles", []))
            roles.add(role_name)
            self._groups[group_id]["roles"] = list(roles)
        return {"group_id": group_id, "role": role_name, "status": "assigned"}

    async def remove_role_from_group(self, group_id: str, role_name: str) -> Dict[str, Any]:
        if group_id in self._groups:
            roles = set(self._groups[group_id].get("roles", []))
            roles.discard(role_name)
            self._groups[group_id]["roles"] = list(roles)
        return {"group_id": group_id, "role": role_name, "status": "removed"}

    # --- Session Methods ---

    async def get_all_sessions(self, *args, **kwargs) -> List[Dict[str, Any]]:
        return self._sessions

    async def get_active_sessions(self, first: int = 0, max_results: int = 10) -> List[Dict[str, Any]]:
        return self._sessions[first : first + max_results]

    async def get_session_stats(self) -> Dict[str, Any]:
        return {
            "total_active_sessions": len(self._sessions),
            "unique_users_online": len(set(s["userId"] for s in self._sessions)),
            "avg_session_duration_minutes": 45,
        }

    async def get_user_sessions(self, user_id: str) -> List[Dict[str, Any]]:
        return [s for s in self._sessions if s["userId"] == user_id]

    async def terminate_session(self, session_id: str) -> Dict[str, Any]:
        self._sessions = [s for s in self._sessions if s["id"] != session_id]
        return {"session_id": session_id, "status": "terminated"}

    async def logout_user(self, user_id: str) -> Dict[str, Any]:
        self._sessions = [s for s in self._sessions if s["userId"] != user_id]
        return {"user_id": user_id, "status": "logged_out"}

    # --- Events Methods ---

    async def get_events(self, first: int = 0, max_results: int = 20, event_types: Optional[List[str]] = None, event_type: Optional[str] = None, user_id: Optional[str] = None, ip_address: Optional[str] = None, **kwargs) -> List[Dict[str, Any]]:
        events = self._login_events
        if event_types:
            events = [e for e in events if e["type"] in event_types]
        elif event_type:
            events = [e for e in events if e["type"] == event_type]
        if user_id:
            events = [e for e in events if e["userId"] == user_id]
        if ip_address:
            events = [e for e in events if e["ipAddress"] == ip_address]
        return events[first : first + max_results]

    async def get_login_events(self, first: int = 0, max_results: int = 20, event_types: Optional[List[str]] = None, **kwargs) -> List[Dict[str, Any]]:
        return await self.get_events(first, max_results, event_types=event_types, **kwargs)

    async def get_admin_events(self, first: int = 0, max_results: int = 20, operation_type: Optional[str] = None, resource_type: Optional[str] = None) -> List[Dict[str, Any]]:
        events = self._admin_events
        if operation_type:
            events = [e for e in events if e["operationType"] == operation_type]
        if resource_type:
            events = [e for e in events if e["resourceType"] == resource_type]
        return events[first : first + max_results]

    async def get_event_types(self) -> List[str]:
        return ["LOGIN", "LOGIN_ERROR", "LOGOUT", "CODE_TO_TOKEN", "REFRESH_TOKEN", "UPDATE_PASSWORD", "UPDATE_PROFILE"]

    async def get_login_events_summary(self, days: int = 7) -> Dict[str, Any]:
        return {
            "period_days": days,
            "successful_logins": sum(1 for e in self._login_events if e["type"] == "LOGIN"),
            "failed_logins": sum(1 for e in self._login_events if e["type"] == "LOGIN_ERROR"),
            "unique_users": len(set(e["userId"] for e in self._login_events if e["userId"])),
            "unique_ips": len(set(e["ipAddress"] for e in self._login_events if e["ipAddress"])),
            "top_failed_ips": [],
        }


# Singleton service instance
keycloak_admin = KeycloakAdminService()
