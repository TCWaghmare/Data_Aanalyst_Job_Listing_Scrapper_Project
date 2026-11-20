"""
Compatibility layer for ApifyClient.
Falls back to a robust requests-based client if native apify_client fails to load
(e.g., when Windows Application Control blocks native compiled DLLs like impit).
"""
import logging
import os
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger("apify_client_compat")

try:
    from apify_client import ApifyClient as _NativeApifyClient
    # Test if it can be instantiated without triggering lazy DLL loads
    _ApifyClientClass = _NativeApifyClient
except Exception as _err:
    logger.warning(f"Native apify_client unavailable ({_err}). Using resilient REST fallback.")
    _ApifyClientClass = None


class _RunResult(dict):
    """Dictionary that also allows attribute access for standard run fields."""
    @property
    def default_dataset_id(self) -> Optional[str]:
        return self.get("defaultDatasetId") or self.get("default_dataset_id")

    @property
    def id(self) -> Optional[str]:
        return self.get("id")


class _DatasetWrapper:
    def __init__(self, dataset_id: str, token: str):
        self.dataset_id = dataset_id
        self.token = token

    def list_items(self):
        import requests
        url = f"https://api.apify.com/v2/datasets/{self.dataset_id}/items"
        params = {"token": self.token, "clean": "true"}
        try:
            resp = requests.get(url, params=params, timeout=30)
            items = resp.json() if resp.status_code == 200 else []
            if not isinstance(items, list):
                items = []
        except Exception as err:
            logger.error(f"Failed to fetch Apify dataset items for {self.dataset_id}: {err}")
            items = []

        class _ItemsHolder:
            def __init__(self, items_list: List[Dict[str, Any]]):
                self.items = items_list

        return _ItemsHolder(items)


class _ActorWrapper:
    def __init__(self, actor_id: str, token: str):
        self.actor_id = actor_id
        self.token = token

    def call(
        self,
        run_input: Optional[Dict[str, Any]] = None,
        max_items: Optional[int] = None,
        memory_mbytes: Optional[int] = None,
        max_total_charge_usd: Optional[Any] = None,
        run_timeout: Optional[Any] = None
    ) -> Optional[_RunResult]:
        import requests
        safe_actor_id = self.actor_id.replace("/", "~")
        url = f"https://api.apify.com/v2/acts/{safe_actor_id}/runs"
        params = {"token": self.token}
        if max_items:
            params["maxItems"] = max_items
        if memory_mbytes:
            params["memory"] = memory_mbytes
        if max_total_charge_usd is not None:
            try:
                params["maxTotalChargeUsd"] = float(max_total_charge_usd)
            except Exception:
                pass

        timeout_sec = 120
        if run_timeout:
            timeout_sec = int(run_timeout.total_seconds()) if hasattr(run_timeout, "total_seconds") else int(run_timeout)
        params["timeout"] = timeout_sec

        try:
            logger.info(f"Triggering Apify actor {self.actor_id} via REST endpoint...")
            resp = requests.post(url, json=run_input or {}, params=params, timeout=30)
            if resp.status_code not in (200, 201):
                logger.error(f"Apify Actor run creation failed ({resp.status_code}): {resp.text}")
                return None

            data = resp.json().get("data", {})
            run_id = data.get("id")
            default_dataset_id = data.get("defaultDatasetId")
            if not run_id:
                return None

            # Poll run until completion or timeout
            start_t = time.time()
            poll_interval = 3
            while time.time() - start_t < timeout_sec:
                time.sleep(poll_interval)
                poll_url = f"https://api.apify.com/v2/acts/{safe_actor_id}/runs/{run_id}"
                poll_resp = requests.get(poll_url, params={"token": self.token}, timeout=15)
                if poll_resp.status_code == 200:
                    run_info = poll_resp.json().get("data", {})
                    status = run_info.get("status")
                    if status in ("SUCCEEDED", "FAILED", "ABORTED", "TIMED-OUT"):
                        final_ds = run_info.get("defaultDatasetId") or default_dataset_id
                        return _RunResult({
                            "id": run_id,
                            "defaultDatasetId": final_ds,
                            "default_dataset_id": final_ds,
                            "status": status
                        })

            return _RunResult({
                "id": run_id,
                "defaultDatasetId": default_dataset_id,
                "default_dataset_id": default_dataset_id,
                "status": "RUNNING"
            })
        except Exception as e:
            logger.error(f"Apify REST execution error: {e}", exc_info=True)
            return None


class FallbackApifyClient:
    def __init__(self, token: Optional[str] = None):
        self.token = token or os.environ.get("APIFY_API_TOKEN", "")

    def actor(self, actor_id: str) -> _ActorWrapper:
        return _ActorWrapper(actor_id, self.token)

    def dataset(self, dataset_id: str) -> _DatasetWrapper:
        return _DatasetWrapper(dataset_id, self.token)


# Export ApifyClient: prefer native if functional, otherwise fallback
if _ApifyClientClass is not None:
    ApifyClient = _ApifyClientClass
else:
    ApifyClient = FallbackApifyClient
