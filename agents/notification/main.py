#!/usr/bin/env python3
"""
Notification Agent
Sends completion notifications and user feedback
"""

import asyncio
import os
import json
import logging
from typing import Dict, Any
from datetime import datetime
from dotenv import load_dotenv

from langchain.chat_models import init_chat_model
from langchain.prompts import ChatPromptTemplate
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain.agents import create_tool_calling_agent, AgentExecutor

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

class ConsoleNotifier:
    """Console-based notification system"""
    
    def __init__(self):
        self.notification_history = []
        
    def send_success_notification(self, transaction_result: Dict[str, Any]) -> str:
        """Generate success notification"""
        notification = f"""
✅ TIP SENT SUCCESSFULLY!
💰 Amount: {transaction_result['amount']} SOL
👤 Recipient: @{transaction_result['recipient']}
💬 Message: {transaction_result.get('message', 'No message')}
🆔 Transaction: {transaction_result['transaction_id']}
🔗 Explorer: {transaction_result.get('explorer_url', 'N/A')}
⏰ Time: {transaction_result.get('timestamp', 'N/A')}
💳 Balance: {transaction_result.get('balance_after', 'N/A')} SOL
"""
        
        # Record notification
        self.notification_history.append({
            'type': 'success',
            'transaction_id': transaction_result['transaction_id'],
            'timestamp': datetime.utcnow().isoformat(),
            'content': notification
        })
        
        return notification
    
    def send_failure_notification(self, error: str, tip_data: Dict[str, Any] = None) -> str:
        """Generate failure notification"""
        notification = f"""
❌ TIP FAILED!
🚫 Error: {error}
💡 Please check your command and try again.
"""
        
        if tip_data:
            notification += f"📝 Tip details: {tip_data['amount']} SOL → @{tip_data['recipient']}\n"
        
        # Record notification
        self.notification_history.append({
            'type': 'failure',
            'error': error,
            'timestamp': datetime.utcnow().isoformat(),
            'content': notification
        })
        
        return notification
    
    def send_validation_failure_notification(self, validation_error: str, tip_data: Dict[str, Any]) -> str:
        """Generate validation failure notification"""
        notification = f"""
❌ TIP VALIDATION FAILED!
🚫 Error: {validation_error}
📝 Tip details: {tip_data['amount']} SOL → @{tip_data['recipient']}
💡 Please check your command and try again.
"""
        
        # Record notification
        self.notification_history.append({
            'type': 'validation_failure',
            'error': validation_error,
            'timestamp': datetime.utcnow().isoformat(),
            'content': notification
        })
        
        return notification
    
    def get_notification_history(self, limit: int = 10) -> list:
        """Get recent notification history"""
        return self.notification_history[-limit:]

def load_config() -> Dict[str, Any]:
    """Load configuration from environment variables"""
    config = {
        "coral_connection_url": os.getenv("CORAL_CONNECTION_URL", "http://localhost:8080"),
        "agent_id": os.getenv("NOTIFICATION_AGENT_ID", "notification"),
        "model_name": os.getenv("MODEL_NAME", "mistral-small"),
        "model_provider": os.getenv("MODEL_PROVIDER", "mistral"),
        "api_key": os.getenv("MISTRAL_API_KEY"),
        "model_temperature": float(os.getenv("MODEL_TEMPERATURE", "0.1")),
        "model_max_tokens": int(os.getenv("MODEL_MAX_TOKENS", "4000")),
        "timeout_ms": float(os.getenv("TIMEOUT_MS", "60000")),
    }
    
    # Validate required fields
    required_fields = ["api_key"]
    missing = [field for field in required_fields if not config[field]]
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")
    
    return config

def get_tools_description(tools) -> str:
    """Generate description of available tools"""
    descriptions = []
    for tool in tools:
        tool_desc = f"Tool: {tool.name}, Schema: {json.dumps(tool.args).replace('{', '{{').replace('}', '}}')}"
        descriptions.append(tool_desc)
    return "\n".join(descriptions)

async def create_notification_agent(coral_tools) -> AgentExecutor:
    """Create notification agent with Mistral AI"""
    
    coral_tools_description = get_tools_description(coral_tools)
    
    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            f"""You are a notification agent for a crypto tipping system.

Your responsibilities:
1. Receive transaction results from transaction agent
2. Receive validation failures from validation agent
3. Generate appropriate notifications (success/failure)
4. Send notifications back to console agent
5. Log all notifications for tracking

Available Coral tools: {coral_tools_description}

Process flow:
1. Use wait_for_mentions to receive transaction results or validation failures
2. Generate appropriate notification based on result type
3. Send notification back to console agent
4. Log notification for tracking

Notification types:
- Success: Transaction completed successfully
- Failure: Transaction failed after validation
- Validation Failed: Tip rejected during validation

Always provide clear, helpful information in notifications.
"""
        ),
        ("placeholder", "{agent_scratchpad}")
    ])
    
    config = load_config()
    
    # Initialize Mistral AI model
    model = init_chat_model(
        model=config["model_name"],
        model_provider=config["model_provider"],
        api_key=config["api_key"],
        temperature=config["model_temperature"],
        max_tokens=config["model_max_tokens"]
    )
    
    agent = create_tool_calling_agent(model, coral_tools, prompt)
    return AgentExecutor(agent=agent, tools=coral_tools, verbose=True)

async def main():
    """Main notification agent loop"""
    print("📢 Starting Notification Agent")
    
    try:
        # Load configuration
        config = load_config()
        
        # Connect to Coral Server
        print("🔗 Connecting to Coral Server...")
        client = MultiServerMCPClient(
            connections={
                "coral": {
                    "transport": "sse",
                    "url": config["coral_connection_url"],
                    "timeout": config["timeout_ms"],
                    "sse_read_timeout": config["timeout_ms"],
                }
            }
        )
        
        coral_tools = await client.get_tools(server_name="coral")
        print(f"✅ Connected to Coral Server with {len(coral_tools)} tools")
        
        # Create notification agent
        agent_executor = await create_notification_agent(coral_tools)
        notifier = ConsoleNotifier()
        
        print("🎯 Notification agent ready!")
        
        # Main notification loop
        while True:
            try:
                # Listen for notification requests
                await agent_executor.ainvoke({
                    "input": "Listen for transaction results and validation failures to send notifications",
                    "agent_scratchpad": []
                })
                await asyncio.sleep(5)
                
            except Exception as e:
                print(f"❌ Notification error: {e}")
                logger.error(f"Notification error: {e}")
                await asyncio.sleep(10)
                
    except Exception as e:
        print(f"💥 Fatal error in notification agent: {e}")
        logger.error(f"Fatal error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())
