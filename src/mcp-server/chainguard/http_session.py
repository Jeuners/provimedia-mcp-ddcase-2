"""
CHAINGUARD MCP Server - HTTP Session Module

Contains: HTTPSessionManager for endpoint testing with auth
Memory-safe with TTL-LRU Cache for sessions

Copyright (c) 2026 Provimedia GmbH
Licensed under the Polyform Noncommercial License 1.0.0
See LICENSE file in the project root for full license information.
"""

import asyncio
import re
from datetime import datetime
from typing import Dict, Any, Optional

from .config import logger, HTTP_REQUEST_TIMEOUT_SECONDS
from .cache import TTLLRUCache

# Session cache settings
MAX_SESSIONS = 50
SESSION_TTL_SECONDS = 86400  # 24 hours

# HTTP Client imports
try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False
    import urllib.request
    import urllib.error
    import urllib.parse
    import http.cookiejar


class HTTPSessionManager:
    """
    Manages HTTP sessions with cookie persistence.
    Handles login flows and maintains auth state.

    Memory-safe: Uses TTL-LRU cache to prevent unbounded growth.
    Sessions expire after 24 hours or when cache is full (50 max).
    """

    def __init__(self):
        self._sessions: TTLLRUCache[Dict[str, Any]] = TTLLRUCache(
            maxsize=MAX_SESSIONS,
            ttl_seconds=SESSION_TTL_SECONDS
        )

    def get_session(self, project_id: str) -> Dict[str, Any]:
        """Get or create session for project."""
        session = self._sessions.get(project_id)
        if session is None:
            session = {
                "cookies": {},
                "csrf_token": None,
                "logged_in": False,
                "base_url": None,
                "last_used": None,
                # v4.15: Store credentials in memory for auto-re-login
                "credentials": {}
            }
            self._sessions.set(project_id, session)
        return session

    def save_session(self, project_id: str, session_data: Dict[str, Any]):
        """Save session data."""
        session_data["last_used"] = datetime.now().isoformat()
        self._sessions.set(project_id, session_data)

    def clear_session(self, project_id: str):
        """Clear session for project."""
        self._sessions.invalidate(project_id)

    def is_logged_in(self, project_id: str) -> bool:
        """Check if session exists and is marked as logged in."""
        session = self._sessions.get(project_id)
        return session is not None and session.get("logged_in", False)

    async def ensure_session(
        self,
        project_id: str,
        base_url: str = ""
    ) -> Dict[str, Any]:
        """
        v4.15: Ensure valid session exists, re-login if needed.

        Uses credentials stored in memory from previous login.

        Args:
            project_id: Project identifier
            base_url: Base URL for the application (for building login URL)

        Returns:
            {"success": True} if session is valid or re-login succeeded
            {"success": False, "error": "..."} if re-login failed or no credentials
        """
        # Check if we have a valid session
        if self.is_logged_in(project_id):
            return {"success": True, "reused": True}

        # Get stored credentials from session cache
        session = self.get_session(project_id)
        credentials = session.get("credentials", {})

        # No valid session - try to re-login if we have credentials
        if not credentials or not credentials.get("username") or not credentials.get("password"):
            return {"success": False, "error": "No credentials stored - login required"}

        login_url = credentials.get("login_url", "")
        if not login_url:
            return {"success": False, "error": "No login_url stored"}

        # Build full login URL if needed
        if not login_url.startswith("http") and base_url:
            login_url = base_url.rstrip("/") + "/" + login_url.lstrip("/")

        # Attempt re-login
        logger.info(f"Auto-re-login for project {project_id}")
        result = await self.login(
            login_url=login_url,
            username=credentials["username"],
            password=credentials["password"],
            project_id=project_id,
            username_field=credentials.get("username_field", "email"),
            password_field=credentials.get("password_field", "password")
        )

        if result["success"]:
            return {"success": True, "reused": False, "auto_relogin": True}

        return {"success": False, "error": f"Auto-re-login failed: {result.get('error', 'Unknown')}"}

    async def test_endpoint(
        self,
        url: str,
        method: str = "GET",
        project_id: str = "",
        data: Optional[Dict] = None,
        headers: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        Test an endpoint with session support.
        Returns response info including auth status detection.
        """
        session = self.get_session(project_id)
        result = {
            "status_code": 0,
            "success": False,
            "needs_auth": False,
            "error": None,
            "body_preview": "",
            "headers": {}
        }

        try:
            if HAS_AIOHTTP:
                result = await self._test_with_aiohttp(url, method, session, data, headers)
            else:
                result = await self._test_with_urllib(url, method, session, data, headers)

            # Detect auth requirements
            if result["status_code"] in [401, 403]:
                result["needs_auth"] = True
                result["error"] = "Authentication required"
            elif result["status_code"] in [301, 302, 303, 307, 308]:
                redirect_url = result["headers"].get("location", "")
                if any(x in redirect_url.lower() for x in ["login", "auth", "signin"]):
                    result["needs_auth"] = True
                    result["error"] = f"Redirect to login: {redirect_url}"
            elif "login" in result["body_preview"].lower() and "form" in result["body_preview"].lower():
                result["needs_auth"] = True
                result["error"] = "Login form detected in response"

            result["success"] = 200 <= result["status_code"] < 300

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"HTTP test error: {e}")

        return result

    async def login(
        self,
        login_url: str,
        username: str,
        password: str,
        project_id: str,
        csrf_field: str = "_token",
        username_field: str = "email",
        password_field: str = "password"
    ) -> Dict[str, Any]:
        """
        Perform login and store session.
        Handles Laravel CSRF tokens automatically.
        """
        session = self.get_session(project_id)
        result = {"success": False, "error": None}

        try:
            if HAS_AIOHTTP:
                async with aiohttp.ClientSession() as http_session:
                    # Step 1: GET login page for CSRF token
                    async with http_session.get(login_url) as resp:
                        html = await resp.text()
                        csrf_token = self._extract_csrf_token(html)
                        session["csrf_token"] = csrf_token

                        for cookie in resp.cookies.values():
                            session["cookies"][cookie.key] = cookie.value

                    # Step 2: POST login
                    login_data = {
                        username_field: username,
                        password_field: password
                    }
                    if csrf_token:
                        login_data[csrf_field] = csrf_token

                    async with http_session.post(
                        login_url,
                        data=login_data,
                        cookies=session["cookies"],
                        allow_redirects=False
                    ) as resp:
                        for cookie in resp.cookies.values():
                            session["cookies"][cookie.key] = cookie.value

                        if resp.status in [301, 302, 303]:
                            redirect = resp.headers.get("location", "")
                            if "login" not in redirect.lower():
                                session["logged_in"] = True
                                result["success"] = True
                                result["redirect"] = redirect
                            else:
                                result["error"] = "Login failed - redirected back to login"
                        elif resp.status == 200:
                            body = await resp.text()
                            if "dashboard" in body.lower() or "welcome" in body.lower():
                                session["logged_in"] = True
                                result["success"] = True
                            else:
                                result["error"] = "Login may have failed - check credentials"
                        else:
                            result["error"] = f"Unexpected status: {resp.status}"

            else:
                result = await asyncio.get_event_loop().run_in_executor(
                    None, self._login_urllib, login_url, username, password,
                    session, csrf_field, username_field, password_field
                )

            if result["success"]:
                # v4.15: Store credentials in memory for auto-re-login
                session["credentials"] = {
                    "username": username,
                    "password": password,
                    "login_url": login_url,
                    "username_field": username_field,
                    "password_field": password_field
                }
                self.save_session(project_id, session)

        except Exception as e:
            result["error"] = str(e)
            logger.error(f"Login error: {e}")

        return result

    def _extract_csrf_token(self, html: str) -> Optional[str]:
        """Extract CSRF token from HTML (Laravel style)."""
        match = re.search(r'name=["\']_token["\'].*?value=["\']([^"\']+)["\']', html, re.IGNORECASE)
        if match:
            return match.group(1)
        match = re.search(r'name=["\']csrf-token["\'].*?content=["\']([^"\']+)["\']', html, re.IGNORECASE)
        if match:
            return match.group(1)
        return None

    async def _test_with_aiohttp(
        self, url: str, method: str, session: Dict, data: Optional[Dict], headers: Optional[Dict]
    ) -> Dict[str, Any]:
        """Test endpoint using aiohttp."""
        result = {"status_code": 0, "headers": {}, "body_preview": "", "needs_auth": False, "error": None}

        async with aiohttp.ClientSession(cookies=session.get("cookies", {})) as http_session:
            req_headers = headers or {}
            if session.get("csrf_token"):
                req_headers["X-CSRF-TOKEN"] = session["csrf_token"]

            kwargs = {"headers": req_headers, "allow_redirects": False}
            if data:
                kwargs["data" if method == "POST" else "json"] = data

            async with http_session.request(method, url, **kwargs) as resp:
                result["status_code"] = resp.status
                result["headers"] = {k.lower(): v for k, v in resp.headers.items()}
                try:
                    body = await resp.text()
                    result["body_preview"] = body[:500]
                except:
                    result["body_preview"] = "[binary content]"

                for cookie in resp.cookies.values():
                    session["cookies"][cookie.key] = cookie.value

        return result

    async def _test_with_urllib(
        self, url: str, method: str, session: Dict, data: Optional[Dict], headers: Optional[Dict]
    ) -> Dict[str, Any]:
        """Fallback: Test endpoint using urllib (sync wrapped in async)."""
        def sync_request():
            result = {"status_code": 0, "headers": {}, "body_preview": "", "needs_auth": False, "error": None}
            try:
                cookie_jar = http.cookiejar.CookieJar()
                opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))

                req_data = None
                if data:
                    req_data = urllib.parse.urlencode(data).encode() if method == "POST" else None

                req = urllib.request.Request(url, data=req_data, method=method)
                for k, v in (headers or {}).items():
                    req.add_header(k, v)

                for name, value in session.get("cookies", {}).items():
                    req.add_header("Cookie", f"{name}={value}")

                with opener.open(req, timeout=HTTP_REQUEST_TIMEOUT_SECONDS) as resp:
                    result["status_code"] = resp.status
                    result["headers"] = {k.lower(): v for k, v in resp.headers.items()}
                    result["body_preview"] = resp.read(500).decode(errors='ignore')

            except urllib.error.HTTPError as e:
                result["status_code"] = e.code
                result["error"] = str(e)
            except Exception as e:
                result["error"] = str(e)

            return result

        return await asyncio.get_event_loop().run_in_executor(None, sync_request)


# Global instance
http_session_manager = HTTPSessionManager()
