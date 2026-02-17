#!/usr/bin/env python3
"""
User rules and preferences storage with persistent memory
"""
import logging
import uuid
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from .config import Config
from .storage import FileStorage

logger = logging.getLogger(__name__)


class RulesManager:
    """Manages persistent user rules and preferences"""

    def __init__(self):
        self.storage = FileStorage(Config.RULES_FILE, Config.BACKUP_DIR)
        self._cache = None
        self._cache_time = None

    def _get_cached_data(self) -> Dict[str, Any]:
        """Get cached rules data or load from file"""
        now = datetime.now()

        # Check cache validity
        if (self._cache is None or
            self._cache_time is None or
            (now - self._cache_time).total_seconds() > Config.CACHE_TTL):

            self._cache = self.storage.read_json()
            self._cache_time = now
            logger.debug("Rules cache refreshed")

        return self._cache

    def _invalidate_cache(self) -> None:
        """Invalidate the rules cache"""
        self._cache = None
        self._cache_time = None

    def save_user_rule(self, rule_text: str, category: str = "general") -> Dict[str, Any]:
        """
        Save a user rule with persistent storage

        Args:
            rule_text: The rule text to save
            category: Category for the rule (default: "general")

        Returns:
            Dict with success status, rule_id, and message
        """
        # Validate input
        is_valid, error_msg = self._validate_rule(rule_text, category)
        if not is_valid:
            logger.warning(f"Rule validation failed: {error_msg}")
            return {
                "success": False,
                "rule_id": None,
                "message": f"Validation error: {error_msg}"
            }

        try:
            # Load current data
            data = self._get_cached_data()

            # Check rule limit
            if len(data.get("rules", [])) >= Config.MAX_RULES:
                return {
                    "success": False,
                    "rule_id": None,
                    "message": f"Maximum rules limit ({Config.MAX_RULES}) reached"
                }

            # Create new rule
            rule_id = str(uuid.uuid4())
            new_rule = {
                "rule_id": rule_id,
                "rule_text": rule_text.strip(),
                "category": category.strip(),
                "created_at": datetime.now().isoformat(),
                "last_referenced_at": datetime.now().isoformat(),
                "reference_count": 0
            }

            # Add to data
            data["rules"].append(new_rule)

            # Save to file
            if self.storage.write_json(data):
                self._invalidate_cache()
                logger.info(f"Rule saved successfully: {rule_id}")

                return {
                    "success": True,
                    "rule_id": rule_id,
                    "message": "Rule saved successfully"
                }
            else:
                return {
                    "success": False,
                    "rule_id": None,
                    "message": "Failed to save rule to storage"
                }

        except Exception as e:
            logger.error(f"Error saving rule: {e}")
            return {
                "success": False,
                "rule_id": None,
                "message": f"Internal error: {str(e)}"
            }

    def get_user_rules(self, category: Optional[str] = None) -> Dict[str, Any]:
        """
        Get user rules, optionally filtered by category

        Args:
            category: Optional category filter

        Returns:
            Dict with rules list and total count
        """
        try:
            data = self._get_cached_data()
            all_rules = data.get("rules", [])

            # Filter by category if specified
            if category:
                filtered_rules = [rule for rule in all_rules if rule.get("category") == category]
            else:
                filtered_rules = all_rules

            # Sort by last_referenced_at descending (most recent first)
            try:
                filtered_rules.sort(
                    key=lambda x: datetime.fromisoformat(x.get("last_referenced_at", "1900-01-01")),
                    reverse=True
                )
            except Exception as e:
                logger.warning(f"Error sorting rules: {e}")
                # Continue with unsorted rules

            # Limit to 100 rules to prevent overwhelming context
            limited_rules = filtered_rules[:100]

            # Update reference stats for returned rules
            if limited_rules:
                self._update_rule_references(limited_rules)

            return {
                "rules": limited_rules,
                "total_count": len(filtered_rules)
            }

        except Exception as e:
            logger.error(f"Error getting rules: {e}")
            return {
                "rules": [],
                "total_count": 0
            }

    def delete_user_rule(self, rule_id: str) -> Dict[str, Any]:
        """
        Delete a user rule by ID

        Args:
            rule_id: UUID of the rule to delete

        Returns:
            Dict with success status and message
        """
        try:
            data = self._get_cached_data()
            rules = data.get("rules", [])

            # Find rule to delete
            rule_to_delete = None
            for i, rule in enumerate(rules):
                if rule.get("rule_id") == rule_id:
                    rule_to_delete = rules.pop(i)
                    break

            if rule_to_delete is None:
                return {
                    "success": False,
                    "message": f"Rule with ID {rule_id} not found"
                }

            # Save updated data
            if self.storage.write_json(data):
                self._invalidate_cache()
                logger.info(f"Rule deleted successfully: {rule_id}")

                return {
                    "success": True,
                    "message": f"Rule '{rule_to_delete.get('rule_text', '')[:50]}...' deleted successfully"
                }
            else:
                return {
                    "success": False,
                    "message": "Failed to save changes to storage"
                }

        except Exception as e:
            logger.error(f"Error deleting rule: {e}")
            return {
                "success": False,
                "message": f"Internal error: {str(e)}"
            }

    def list_rule_categories(self) -> Dict[str, Any]:
        """
        List all unique rule categories

        Returns:
            Dict with categories list and counts
        """
        try:
            data = self._get_cached_data()
            rules = data.get("rules", [])

            # Count rules by category
            category_counts = {}
            for rule in rules:
                category = rule.get("category", "general")
                category_counts[category] = category_counts.get(category, 0) + 1

            return {
                "categories": list(category_counts.keys()),
                "category_counts": category_counts,
                "total_categories": len(category_counts)
            }

        except Exception as e:
            logger.error(f"Error listing categories: {e}")
            return {
                "categories": [],
                "category_counts": {},
                "total_categories": 0
            }

    def _validate_rule(self, rule_text: str, category: str) -> Tuple[bool, str]:
        """
        Validate rule input

        Args:
            rule_text: Rule text to validate
            category: Category to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        if not rule_text or len(rule_text.strip()) == 0:
            return False, "Rule text cannot be empty"

        if len(rule_text) > 1000:
            return False, "Rule text must be less than 1000 characters"

        if category and len(category) > 50:
            return False, "Category must be less than 50 characters"

        return True, "Valid"

    def _update_rule_references(self, rules: List[Dict[str, Any]]) -> None:
        """
        Update last_referenced_at and reference_count for rules

        Args:
            rules: List of rules that were referenced
        """
        try:
            data = self._get_cached_data()
            all_rules = data.get("rules", [])
            current_time = datetime.now().isoformat()

            updated = False

            # Update reference stats for each returned rule
            for returned_rule in rules:
                rule_id = returned_rule.get("rule_id")
                for rule in all_rules:
                    if rule.get("rule_id") == rule_id:
                        rule["last_referenced_at"] = current_time
                        rule["reference_count"] = rule.get("reference_count", 0) + 1
                        updated = True
                        break

            # Save if any rules were updated
            if updated:
                self.storage.write_json(data)
                self._invalidate_cache()
                logger.debug(f"Updated reference stats for {len(rules)} rules")

        except Exception as e:
            logger.warning(f"Error updating rule references: {e}")
            # Don't fail the main operation if this fails