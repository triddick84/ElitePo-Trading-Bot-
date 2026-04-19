"""
Signal Routing Service
======================
Routes trading signals to configured destinations (Pocket Option, MT5, Telegram)
based on user-defined rules with asset/confidence/session filters.
"""

import logging
from typing import Dict, List, Optional
from datetime import datetime, timezone
from motor.motor_asyncio import AsyncIOMotorDatabase

logger = logging.getLogger(__name__)


class SignalRouter:
    def __init__(self, db: AsyncIOMotorDatabase):
        self.db = db
        self.collection = db["signal_routing_rules"]
        self.log_collection = db["signal_routing_log"]

    async def get_rules(self) -> List[Dict]:
        rules = await self.collection.find({}, {"_id": 0}).sort("priority", 1).to_list(100)
        return rules

    async def get_rule(self, rule_id: str) -> Optional[Dict]:
        return await self.collection.find_one({"rule_id": rule_id}, {"_id": 0})

    async def create_rule(self, rule: Dict) -> Dict:
        rule["created_at"] = datetime.now(timezone.utc).isoformat()
        rule["updated_at"] = rule["created_at"]
        rule.setdefault("enabled", True)
        rule.setdefault("priority", 50)
        await self.collection.insert_one(rule)
        return {k: v for k, v in rule.items() if k != "_id"}

    async def update_rule(self, rule_id: str, updates: Dict) -> Optional[Dict]:
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        result = await self.collection.find_one_and_update(
            {"rule_id": rule_id},
            {"$set": updates},
            return_document=True,
            projection={"_id": 0}
        )
        return result

    async def delete_rule(self, rule_id: str) -> bool:
        result = await self.collection.delete_one({"rule_id": rule_id})
        return result.deleted_count > 0

    async def route_signal(self, signal: Dict) -> Dict:
        """
        Route a signal through all enabled rules and return matched destinations.
        """
        rules = await self.get_rules()
        matched = []
        destinations = set()

        for rule in rules:
            if not rule.get("enabled", True):
                continue
            if self._matches(rule, signal):
                matched.append(rule["rule_id"])
                for dest in rule.get("destinations", []):
                    destinations.add(dest)

        # Default: if no rules match, send to all enabled destinations
        if not matched:
            destinations = {"pocket_option", "telegram"}

        result = {
            "signal": {k: v for k, v in signal.items() if k != "_id"},
            "matched_rules": matched,
            "destinations": list(destinations),
            "routed_at": datetime.now(timezone.utc).isoformat()
        }

        # Log the routing
        await self.log_collection.insert_one({
            **result,
            "signal_direction": signal.get("direction"),
            "signal_symbol": signal.get("symbol"),
            "signal_confidence": signal.get("confidence"),
        })

        return {k: v for k, v in result.items() if k != "_id"}

    def _matches(self, rule: Dict, signal: Dict) -> bool:
        filters = rule.get("filters", {})

        # Asset filter
        assets = filters.get("assets", [])
        if assets:
            sig_symbol = (signal.get("symbol") or "").upper()
            if not any(a.upper() in sig_symbol or sig_symbol in a.upper() for a in assets):
                return False

        # Min confidence filter
        min_conf = filters.get("min_confidence")
        if min_conf is not None:
            if (signal.get("confidence") or 0) < min_conf:
                return False

        # Max confidence filter
        max_conf = filters.get("max_confidence")
        if max_conf is not None:
            if (signal.get("confidence") or 0) > max_conf:
                return False

        # Direction filter
        directions = filters.get("directions", [])
        if directions:
            if (signal.get("direction") or "").upper() not in [d.upper() for d in directions]:
                return False

        # Strategy filter
        strategies = filters.get("strategies", [])
        if strategies:
            sig_strat = (signal.get("strategy") or signal.get("analysis_type") or "").lower()
            if not any(s.lower() in sig_strat for s in strategies):
                return False

        # Session filter
        sessions = filters.get("sessions", [])
        if sessions:
            hour = datetime.now(timezone.utc).hour
            current_session = "off_hours"
            if 13 <= hour < 16:
                current_session = "overlap"
            elif 8 <= hour < 16:
                current_session = "london"
            elif 13 <= hour < 21:
                current_session = "new_york"
            elif 0 <= hour < 8:
                current_session = "asian"
            if current_session not in sessions:
                return False

        return True

    async def get_routing_log(self, limit: int = 50) -> List[Dict]:
        logs = await self.log_collection.find(
            {}, {"_id": 0}
        ).sort("routed_at", -1).limit(limit).to_list(limit)
        return logs

    async def get_routing_stats(self) -> Dict:
        total = await self.log_collection.count_documents({})
        rules = await self.collection.count_documents({})
        enabled = await self.collection.count_documents({"enabled": True})

        # Count by destination
        pipeline = [
            {"$unwind": "$destinations"},
            {"$group": {"_id": "$destinations", "count": {"$sum": 1}}}
        ]
        dest_counts = {}
        async for doc in self.log_collection.aggregate(pipeline):
            dest_counts[doc["_id"]] = doc["count"]

        return {
            "total_routed": total,
            "total_rules": rules,
            "enabled_rules": enabled,
            "by_destination": dest_counts
        }


_signal_router = None

def get_signal_router(db: AsyncIOMotorDatabase) -> SignalRouter:
    global _signal_router
    if _signal_router is None:
        _signal_router = SignalRouter(db)
    return _signal_router
