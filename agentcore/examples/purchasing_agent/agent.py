"""Purchasing Agent implementation."""

from typing import AsyncIterator

from agentcore import (
    AgentInfo,
    RequestContext,
    Message,
    InferenceClient,
    InferenceResponse,
)


SYSTEM_PROMPT = """You are the Purchasing Agent, an expert in procurement and purchase order management.

You help users with:
- Searching and viewing purchase orders
- Creating new purchase orders
- Analyzing spend by vendor, category, or time period
- Vendor management and lookup

Always be helpful and provide clear, actionable responses. When searching for data,
describe what you found and offer relevant follow-up actions.

If you need to call a tool, explain what you're doing before calling it.
"""


class PurchasingAgent:
    """Domain agent for purchasing/procurement tasks."""

    def __init__(self, inference: InferenceClient):
        self._inference = inference
        self._tools = self._get_tools()

    @property
    def info(self) -> AgentInfo:
        return AgentInfo(
            agent_id="purchasing",
            name="Purchasing Agent",
            description="""Purchasing domain expert that handles:
            - Purchase order creation, search, and management
            - Vendor lookup and management
            - Catalog item search
            - Spend analysis and reporting""",
            base_url="http://localhost:8001",
            capabilities=["search", "create", "update", "approve", "analyze"],
            domains=["purchase_order", "vendor", "catalog"],
            example_queries=[
                "Find PO 12345",
                "Create a purchase order for office supplies",
                "What's my spend on IT equipment this quarter?",
                "Show vendors for category Office Supplies",
            ],
            version="1.0.0",
            team="Procurement",
        )

    def _get_tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "search_purchase_orders",
                    "description": "Search for purchase orders by various criteria",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "po_number": {
                                "type": "string",
                                "description": "Specific PO number to find",
                            },
                            "vendor_name": {
                                "type": "string",
                                "description": "Vendor name to filter by",
                            },
                            "status": {
                                "type": "string",
                                "enum": ["draft", "submitted", "approved", "received", "cancelled"],
                                "description": "PO status to filter by",
                            },
                            "date_from": {
                                "type": "string",
                                "description": "Start date (YYYY-MM-DD)",
                            },
                            "date_to": {
                                "type": "string",
                                "description": "End date (YYYY-MM-DD)",
                            },
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_spend_analysis",
                    "description": "Get spend analysis by category, vendor, or time period",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "group_by": {
                                "type": "string",
                                "enum": ["vendor", "category", "month", "quarter"],
                                "description": "How to group the spend data",
                            },
                            "period": {
                                "type": "string",
                                "description": "Time period (e.g., 'Q1 2026', 'last 6 months')",
                            },
                        },
                        "required": ["group_by"],
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "search_vendors",
                    "description": "Search for vendors by name or category",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "name": {
                                "type": "string",
                                "description": "Vendor name to search for",
                            },
                            "category": {
                                "type": "string",
                                "description": "Category to filter vendors by",
                            },
                        },
                    },
                },
            },
        ]

    async def handle_query(
        self,
        ctx: RequestContext,
        query: str,
    ) -> AsyncIterator[str]:
        """Handle a user query and stream the response."""
        messages = [
            Message.system(SYSTEM_PROMPT),
            Message.user(query),
        ]

        response = await self._inference.complete(messages, tools=self._tools)

        if response.has_tool_calls:
            for tc in response.tool_calls or []:
                yield f"[Calling tool: {tc.name}]\n"
                tool_result = await self._execute_tool(ctx, tc.name, tc.arguments)
                yield f"[Tool result received]\n\n"
                
                messages.append(response.to_message())
                messages.append(Message.tool(tc.id, tool_result, tc.name))
            
            final_response = await self._inference.complete(messages)
            if final_response.content:
                yield final_response.content
        else:
            if response.content:
                yield response.content

    async def _execute_tool(
        self,
        ctx: RequestContext,
        tool_name: str,
        arguments: dict,
    ) -> str:
        """Execute a tool and return the result."""
        if tool_name == "search_purchase_orders":
            return self._mock_search_pos(arguments)
        elif tool_name == "get_spend_analysis":
            return self._mock_spend_analysis(arguments)
        elif tool_name == "search_vendors":
            return self._mock_search_vendors(arguments)
        else:
            return f"Unknown tool: {tool_name}"

    def _mock_search_pos(self, args: dict) -> str:
        if po_num := args.get("po_number"):
            return f"""Found 1 purchase order:

PO Number: {po_num}
Status: Approved
Vendor: Acme Supplies Inc.
Total: $5,234.00
Created: 2026-01-10
Items: 3 line items
- Office Chairs (qty: 10) - $2,500.00
- Standing Desks (qty: 5) - $2,500.00  
- Monitor Arms (qty: 10) - $234.00"""
        else:
            return """Found 5 purchase orders matching criteria:

1. PO-2026-001 | Acme Supplies | $5,234.00 | Approved
2. PO-2026-002 | Tech Solutions | $12,500.00 | Submitted
3. PO-2026-003 | Office Depot | $890.00 | Approved
4. PO-2026-004 | Dell Inc | $45,000.00 | Draft
5. PO-2026-005 | Staples | $567.00 | Received"""

    def _mock_spend_analysis(self, args: dict) -> str:
        group_by = args.get("group_by", "category")
        period = args.get("period", "Q1 2026")
        
        if group_by == "vendor":
            return f"""Spend Analysis by Vendor ({period}):

1. Dell Inc: $125,000 (35%)
2. Acme Supplies: $45,000 (13%)
3. Tech Solutions: $38,000 (11%)
4. Office Depot: $25,000 (7%)
5. Others: $122,000 (34%)

Total Spend: $355,000"""
        else:
            return f"""Spend Analysis by Category ({period}):

1. IT Equipment: $180,000 (51%)
2. Office Supplies: $65,000 (18%)
3. Furniture: $55,000 (15%)
4. Software: $35,000 (10%)
5. Other: $20,000 (6%)

Total Spend: $355,000"""

    def _mock_search_vendors(self, args: dict) -> str:
        category = args.get("category", "")
        name = args.get("name", "")
        
        return f"""Found 4 vendors{' for ' + category if category else ''}:

1. Acme Supplies Inc.
   - Categories: Office Supplies, Furniture
   - Rating: 4.5/5 | On-time: 98%
   
2. Tech Solutions Corp
   - Categories: IT Equipment, Software
   - Rating: 4.8/5 | On-time: 95%
   
3. Office Depot
   - Categories: Office Supplies
   - Rating: 4.2/5 | On-time: 92%
   
4. Dell Inc
   - Categories: IT Equipment, Hardware
   - Rating: 4.7/5 | On-time: 97%"""
