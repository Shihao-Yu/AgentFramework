"""Payables Agent implementation."""

from typing import AsyncIterator

from agentcore import (
    AgentInfo,
    RequestContext,
    Message,
    InferenceClient,
)


SYSTEM_PROMPT = """You are the Payables Agent, an expert in accounts payable and invoice processing.

You help users with:
- Invoice lookup and status inquiries
- Payment scheduling and status
- Vendor payment history
- AP aging reports and analysis

Always be helpful and provide clear, actionable responses. When searching for data,
describe what you found and offer relevant follow-up actions.

If you need to call a tool, explain what you're doing before calling it.
"""


class PayablesAgent:
    """Domain agent for accounts payable tasks."""

    def __init__(self, inference: InferenceClient):
        self._inference = inference
        self._tools = self._get_tools()

    @property
    def info(self) -> AgentInfo:
        return AgentInfo(
            agent_id="payables",
            name="Payables Agent",
            description="""Accounts payable expert that handles:
            - Invoice processing and status lookup
            - Payment scheduling and execution
            - Vendor payment inquiries
            - AP aging and reporting""",
            base_url="http://localhost:8002",
            capabilities=["search", "process", "pay", "report"],
            domains=["invoice", "payment", "vendor_payment"],
            example_queries=[
                "Show unpaid invoices for vendor ACME",
                "When will invoice INV-789 be paid?",
                "What's the AP aging summary?",
                "Show payment history for Dell",
            ],
            version="1.0.0",
            team="Finance",
        )

    def _get_tools(self) -> list[dict]:
        return [
            {
                "type": "function",
                "function": {
                    "name": "search_invoices",
                    "description": "Search for invoices by various criteria",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "invoice_number": {
                                "type": "string",
                                "description": "Specific invoice number to find",
                            },
                            "vendor_name": {
                                "type": "string",
                                "description": "Vendor name to filter by",
                            },
                            "status": {
                                "type": "string",
                                "enum": ["pending", "approved", "paid", "disputed"],
                                "description": "Invoice status to filter by",
                            },
                            "po_number": {
                                "type": "string",
                                "description": "Related PO number",
                            },
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_payment_status",
                    "description": "Get payment status for an invoice or payment batch",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "invoice_number": {
                                "type": "string",
                                "description": "Invoice number to check",
                            },
                            "payment_id": {
                                "type": "string",
                                "description": "Payment batch ID to check",
                            },
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_ap_aging",
                    "description": "Get accounts payable aging report",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "vendor_name": {
                                "type": "string",
                                "description": "Filter by vendor (optional)",
                            },
                            "as_of_date": {
                                "type": "string",
                                "description": "Aging as of date (YYYY-MM-DD)",
                            },
                        },
                    },
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "get_vendor_payment_history",
                    "description": "Get payment history for a vendor",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "vendor_name": {
                                "type": "string",
                                "description": "Vendor name",
                            },
                            "period": {
                                "type": "string",
                                "description": "Time period (e.g., 'last 6 months')",
                            },
                        },
                        "required": ["vendor_name"],
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
        if tool_name == "search_invoices":
            return self._mock_search_invoices(arguments)
        elif tool_name == "get_payment_status":
            return self._mock_payment_status(arguments)
        elif tool_name == "get_ap_aging":
            return self._mock_ap_aging(arguments)
        elif tool_name == "get_vendor_payment_history":
            return self._mock_payment_history(arguments)
        else:
            return f"Unknown tool: {tool_name}"

    def _mock_search_invoices(self, args: dict) -> str:
        if inv_num := args.get("invoice_number"):
            return f"""Found invoice {inv_num}:

Invoice: {inv_num}
Vendor: Acme Supplies Inc.
Amount: $5,234.00
Status: Approved - Scheduled for payment
PO Reference: PO-2026-001
Invoice Date: 2026-01-05
Due Date: 2026-02-04
Payment Date: 2026-01-20 (scheduled)"""
        
        vendor = args.get("vendor_name", "")
        status = args.get("status", "")
        
        return f"""Found 5 invoices{' for ' + vendor if vendor else ''}{' with status ' + status if status else ''}:

1. INV-2026-001 | Acme Supplies | $5,234.00 | Approved
2. INV-2026-002 | Tech Solutions | $12,500.00 | Pending
3. INV-2026-003 | Office Depot | $890.00 | Paid
4. INV-2026-004 | Dell Inc | $45,000.00 | Approved
5. INV-2026-005 | Staples | $567.00 | Disputed"""

    def _mock_payment_status(self, args: dict) -> str:
        inv = args.get("invoice_number", "INV-001")
        return f"""Payment Status for {inv}:

Status: Scheduled
Scheduled Payment Date: 2026-01-20
Payment Method: ACH Transfer
Amount: $5,234.00
Vendor Bank: Chase ****1234

Payment will be processed in the next payment run (Jan 20, 2026).
Expected clearing: 2-3 business days after payment date."""

    def _mock_ap_aging(self, args: dict) -> str:
        vendor = args.get("vendor_name", "")
        date = args.get("as_of_date", "2026-01-14")
        
        if vendor:
            return f"""AP Aging for {vendor} (as of {date}):

Current (0-30 days):    $15,234.00
31-60 days:             $8,500.00
61-90 days:             $0.00
Over 90 days:           $0.00
─────────────────────────────────
Total Outstanding:      $23,734.00

Payment Terms: Net 30
Average Days to Pay: 28 days"""
        
        return f"""AP Aging Summary (as of {date}):

                      Current    31-60     61-90    Over 90    Total
───────────────────────────────────────────────────────────────────
Acme Supplies        $15,234   $8,500       $0        $0   $23,734
Tech Solutions       $12,500       $0       $0        $0   $12,500
Dell Inc             $45,000  $22,000       $0        $0   $67,000
Office Depot          $2,890   $1,200     $450        $0    $4,540
Others               $18,376   $5,300   $2,100      $800   $26,576
───────────────────────────────────────────────────────────────────
TOTAL                $94,000  $37,000   $2,550      $800  $134,350

Vendors with balances over 60 days: 3
Average days payable outstanding: 32 days"""

    def _mock_payment_history(self, args: dict) -> str:
        vendor = args.get("vendor_name", "Vendor")
        period = args.get("period", "last 6 months")
        
        return f"""Payment History for {vendor} ({period}):

Date        | Invoice      | Amount     | Method  | Status
──────────────────────────────────────────────────────────
2026-01-05  | INV-2025-089 | $8,500.00  | ACH     | Cleared
2025-12-20  | INV-2025-078 | $12,340.00 | ACH     | Cleared
2025-12-05  | INV-2025-067 | $5,670.00  | Check   | Cleared
2025-11-20  | INV-2025-056 | $9,800.00  | ACH     | Cleared
2025-11-05  | INV-2025-045 | $7,230.00  | ACH     | Cleared

Summary:
- Total Payments: 5
- Total Amount: $43,540.00
- Average Payment: $8,708.00
- Payment Methods: ACH (80%), Check (20%)"""
