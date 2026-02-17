#!/usr/bin/env python3
"""
Conversation summarizer for extracting key points and action items
"""
import logging
import re
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)


class Summarizer:
    """Summarizes conversations and extracts action items"""

    def __init__(self):
        # Patterns to identify action items
        self.action_patterns = [
            r'\b(?:TODO|TODO:|To do|To-do)\s*[:\-]?\s*(.+)',
            r'\b(?:I need to|I should|I will|I must)\s+(.+)',
            r'\b(?:Action item|Action|Task)\s*[:\-]?\s*(.+)',
            r'\b(?:Follow up|Follow-up)\s*[:\-]?\s*(.+)',
            r'\b(?:Next step|Next steps)\s*[:\-]?\s*(.+)',
        ]

    async def summarize_conversation(
        self,
        conversation_context: Optional[Dict[str, Any]] = None,
        max_points: int = 5
    ) -> Dict[str, Any]:
        """
        Summarize conversation and extract key points

        Args:
            conversation_context: Full conversation context from MCP
            max_points: Maximum number of key points to extract

        Returns:
            Dict with summary, key points, action items, and metadata
        """
        if not conversation_context or not conversation_context.get("messages"):
            return {
                "summary": "No conversation to summarize",
                "key_points": [],
                "action_items": [],
                "conversation_length": "0 messages"
            }

        try:
            messages = conversation_context.get("messages", [])
            return self._analyze_messages(messages, max_points)

        except Exception as e:
            logger.error(f"Error summarizing conversation: {e}")
            return {
                "summary": "Error occurred while summarizing conversation",
                "key_points": [f"Error: {str(e)}"],
                "action_items": [],
                "conversation_length": "unknown"
            }

    def _analyze_messages(self, messages: List[Dict[str, Any]], max_points: int) -> Dict[str, Any]:
        """
        Analyze messages to extract key information

        Args:
            messages: List of conversation messages
            max_points: Maximum key points to extract

        Returns:
            Summary analysis results
        """
        user_messages = []
        assistant_messages = []
        topics = set()
        action_items = []

        # Process messages
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")

            if not content:
                continue

            if role == "user":
                user_messages.append(content)
            elif role == "assistant":
                assistant_messages.append(content)

            # Extract action items
            action_items.extend(self._extract_action_items(content))

            # Extract potential topics
            topics.update(self._extract_topics(content))

        # Generate summary
        summary = self._generate_summary(user_messages, assistant_messages, topics)

        # Generate key points
        key_points = self._generate_key_points(user_messages, assistant_messages, topics, max_points)

        # Clean and limit action items
        action_items = self._clean_action_items(action_items, max_points)

        return {
            "summary": summary,
            "key_points": key_points,
            "action_items": action_items,
            "conversation_length": f"approximately {len(messages)} messages"
        }

    def _extract_action_items(self, text: str) -> List[str]:
        """Extract action items from text using patterns"""
        action_items = []

        for pattern in self.action_patterns:
            matches = re.finditer(pattern, text, re.IGNORECASE | re.MULTILINE)
            for match in matches:
                item = match.group(1).strip()
                if item and len(item) > 5:  # Minimum length filter
                    action_items.append(item)

        return action_items

    def _extract_topics(self, text: str) -> set:
        """Extract potential topics from text"""
        topics = set()

        # Look for capitalized words (potential topics)
        words = re.findall(r'\b[A-Z][a-zA-Z]{2,}\b', text)
        for word in words:
            # Skip common words
            if word.lower() not in ['The', 'This', 'That', 'These', 'Those', 'When', 'Where', 'What', 'Why', 'How']:
                topics.add(word)

        # Look for quoted terms
        quoted = re.findall(r'"([^"]+)"', text)
        topics.update(quoted)

        # Look for code/technical terms
        code_terms = re.findall(r'`([^`]+)`', text)
        topics.update(code_terms)

        return topics

    def _generate_summary(self, user_messages: List[str], assistant_messages: List[str], topics: set) -> str:
        """Generate a concise summary"""
        if not user_messages and not assistant_messages:
            return "Empty conversation"

        # Create basic summary
        if topics:
            topic_list = list(topics)[:3]  # Top 3 topics
            if len(topic_list) == 1:
                summary = f"Discussion about {topic_list[0]}"
            else:
                topics_str = ", ".join(topic_list[:-1]) + f" and {topic_list[-1]}"
                summary = f"Discussion covering {topics_str}"
        else:
            summary = "General conversation"

        # Add context about interaction type
        if len(user_messages) > len(assistant_messages):
            summary += " with multiple user queries"
        elif len(assistant_messages) > len(user_messages):
            summary += " with detailed responses"

        return summary

    def _generate_key_points(
        self,
        user_messages: List[str],
        assistant_messages: List[str],
        topics: set,
        max_points: int
    ) -> List[str]:
        """Generate key points from conversation"""
        key_points = []

        # Add topic-based points
        topic_list = list(topics)[:max_points]
        for topic in topic_list:
            if len(topic) > 2:  # Skip very short topics
                key_points.append(f"Discussion of {topic}")

        # Add interaction-based points
        if user_messages:
            if len(user_messages) > 5:
                key_points.append("Extended conversation with multiple questions")
            elif any(len(msg) > 100 for msg in user_messages):
                key_points.append("Detailed user queries provided")

        if assistant_messages:
            if any("error" in msg.lower() for msg in assistant_messages):
                key_points.append("Error handling and troubleshooting discussed")

        # Limit to max_points
        return key_points[:max_points]

    def _clean_action_items(self, action_items: List[str], max_items: int) -> List[str]:
        """Clean and deduplicate action items"""
        if not action_items:
            return []

        # Remove duplicates while preserving order
        seen = set()
        cleaned = []
        for item in action_items:
            item_clean = item.strip().lower()
            if item_clean not in seen and len(item) > 10:  # Min length filter
                seen.add(item_clean)
                cleaned.append(item.strip())

        return cleaned[:max_items]

    async def analyze_messages(
        self,
        messages: List[Dict[str, Any]],
        analysis_type: str = "summary",
        filter_keywords: List[str] = None
    ) -> Dict[str, Any]:
        """
        Analyze a collection of messages from any source

        Args:
            messages: List of message objects with text, author, timestamp, channel
            analysis_type: Type of analysis to perform
            filter_keywords: Optional keywords to focus on

        Returns:
            Analysis results based on type
        """
        if filter_keywords is None:
            filter_keywords = []

        if not messages:
            return {
                "status": "error",
                "message": "No messages provided for analysis"
            }

        logger.info(f"Analyzing {len(messages)} messages (type: {analysis_type})")

        # Extract message texts for analysis
        message_texts = []
        authors = set()
        channels = set()

        for msg in messages:
            if isinstance(msg, dict):
                text = msg.get("text", "")
                author = msg.get("author", "unknown")
                channel = msg.get("channel", "unknown")

                message_texts.append(text)
                authors.add(author)
                channels.add(channel)

        # Perform analysis based on type
        if analysis_type == "summary":
            result = self._generate_message_summary(message_texts, authors, channels)
        elif analysis_type == "action-items":
            result = self._extract_all_action_items(message_texts)
        elif analysis_type == "key-topics":
            result = self._extract_key_topics(message_texts)
        elif analysis_type == "urgent-items":
            result = self._identify_urgent_items(message_texts)
        elif analysis_type == "full-report":
            result = self._generate_full_report(message_texts, authors, channels, filter_keywords)
        else:
            result = {"error": f"Unknown analysis type: {analysis_type}"}

        # Add metadata
        result["messages_analyzed"] = len(messages)
        result["authors"] = list(authors)[:10]
        result["channels"] = list(channels)
        result["analysis_type"] = analysis_type

        # Add data quality warnings
        if len(messages) < 50:
            result["data_quality_warning"] = f"Only {len(messages)} messages analyzed. Pattern detection requires minimum 50-100+ messages for statistical validity."
        elif len(messages) < 100:
            result["data_quality_notice"] = f"Only {len(messages)} messages analyzed. For optimal pattern detection and trend analysis, 100+ messages recommended."
        else:
            result["data_quality_status"] = f"Good dataset size: {len(messages)} messages provide sufficient data for statistical analysis."

        return result

    def _generate_message_summary(
        self,
        message_texts: List[str],
        authors: set,
        channels: set
    ) -> Dict[str, Any]:
        """Generate a concise summary of messages"""
        total_length = sum(len(text) for text in message_texts)
        avg_length = total_length // len(message_texts) if message_texts else 0

        # Extract topics
        all_text = " ".join(message_texts)
        topics = self._extract_topics(all_text)

        return {
            "summary": f"Analyzed {len(message_texts)} messages from {len(authors)} authors across {len(channels)} channels",
            "key_topics": list(topics)[:5],
            "average_message_length": avg_length,
            "total_characters": total_length
        }

    def _extract_all_action_items(self, message_texts: List[str]) -> Dict[str, Any]:
        """Extract all action items from messages"""
        all_actions = []
        for text in message_texts:
            actions = self._extract_action_items(text)
            all_actions.extend(actions)

        return {
            "action_items": all_actions[:20],  # Limit to 20
            "total_found": len(all_actions)
        }

    def _extract_key_topics(self, message_texts: List[str]) -> Dict[str, Any]:
        """Extract key topics from messages"""
        all_text = " ".join(message_texts)
        topics = self._extract_topics(all_text)

        return {
            "key_topics": list(topics)[:15],
            "total_topics_found": len(topics)
        }

    def _identify_urgent_items(self, message_texts: List[str]) -> Dict[str, Any]:
        """Identify urgent or high-priority items"""
        urgent_indicators = ['urgent', 'asap', 'critical', 'important', 'priority', 'emergency']
        urgent_messages = []

        for text in message_texts:
            if any(indicator in text.lower() for indicator in urgent_indicators):
                urgent_messages.append(text[:200])  # Truncate to 200 chars

        return {
            "urgent_items": urgent_messages[:10],
            "urgent_count": len(urgent_messages)
        }

    def _generate_full_report(
        self,
        message_texts: List[str],
        authors: set,
        channels: set,
        filter_keywords: List[str]
    ) -> Dict[str, Any]:
        """Generate a comprehensive report"""
        all_text = " ".join(message_texts)

        # Apply keyword filtering if specified
        if filter_keywords:
            filtered_messages = [
                text for text in message_texts
                if any(keyword.lower() in text.lower() for keyword in filter_keywords)
            ]
            relevant_count = len(filtered_messages)
        else:
            filtered_messages = message_texts
            relevant_count = len(message_texts)

        return {
            "total_messages": len(message_texts),
            "relevant_messages": relevant_count,
            "authors": list(authors)[:10],
            "channels": list(channels),
            "key_topics": list(self._extract_topics(all_text))[:10],
            "action_items": self._extract_all_action_items(filtered_messages)["action_items"][:5],
            "filter_keywords": filter_keywords if filter_keywords else "none"
        }
