#!/usr/bin/env python3
"""
Transaction Agent
Executes simulated SOL transfers for validated tips
"""

import asyncio
import os
import json
import time
import uuid
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

class MockTransactionExecutor:
    """Simulated SOL transaction executor"""
    
    def __init__(self):
        self.transaction_history = []
        self.balance = float(os.getenv('INITIAL_BALANCE', '100.0'))
        
    def execute_tip(self, tip_data: Dict[str, Any]) -> Dict[str, Any]:
        """Simulate SOL transaction execution"""
        amount = tip_data['amount']
        recipient = tip_data['recipient']
        message = tip_data.get('message', '')
        
        print(f"🔄 Executing transaction: {amount} SOL → @{recipient}")
        
        # Simulate processing time
        time.sleep(2)
        
        # Check balance
        if amount > self.balance:
            return {
                'success': False,
                'error': f'Insufficient balance. Required: {amount} SOL, Available: {self.balance} SOL',
                'transaction_id': None
            }
        
        # Generate mock transaction ID
        tx_id = f"mock_tx_{uuid.uuid4().hex[:8]}"
        
        # Simulate transaction execution
        self.balance -= amount
        
        transaction_result = {
            'success': True,
            'transaction_id': tx_id,
            'amount': amount,
            'recipient': recipient,
            'message': message,
            'timestamp': datetime.utcnow().isoformat(),
            'explorer_url': f"https://explorer.solana.com/tx/{tx_id}?cluster=devnet",
            'balance_after': self.balance
        }
        
        # Record transaction
        self.transaction_history.append(transaction_result)
        
        print(f"✅ Transaction completed: {tx_id}")
        return transaction_result
    
    def get_transaction_status(self, transaction_id: str) -> Dict[str, Any]:
        """Get transaction status"""
        for tx in self.transaction_history:
            if tx['transaction_id'] == transaction_id:
                return {
                    'found': True,
                    'confirmed': tx['success'],
                    'details': tx
                }
        
        return {
            'found': False,
            'confirmed': False,
            'error': 'Transaction not found'
        }
    
    def get_balance(self) -> float:
        """Get current balance"""
        return self.balance

def load_config() -> Dict[str, Any]:
    """Load configuration from environment variables"""
    config = {
        "coral_connection_url": os.getenv("CORAL_CONNECTION_URL", "http://localhost:5555"),
        "agent_id": os.getenv("TRANSACTION_AGENT_ID", "transaction"),
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

async def create_transaction_agent(coral_tools) -> AgentExecutor:
    """Create transaction agent with Mistral AI"""
    
    coral_tools_description = get_tools_description(coral_tools)
    
    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            f"""You are a transaction execution agent for a crypto tipping system.

Your responsibilities:
1. Receive validated tip data from validation agent
2. Execute SOL transfer transactions (simulated)
3. Generate transaction IDs and confirmations
4. Send transaction results to notification agent
5. Handle transaction failures gracefully

Available Coral tools: {coral_tools_description}

Process flow:
1. Use wait_for_mentions to receive validated tip data
2. Execute the SOL transfer (simulated)
3. Generate transaction ID and confirmation
4. Create thread with notification agent
5. Send transaction result to notification agent
6. Respond back to sender with transaction details

Transaction execution:
- Check balance before execution
- Generate unique transaction ID
- Simulate processing time
- Update balance after execution
- Record transaction in history

Always provide detailed transaction information in responses.
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
    """Main transaction agent loop"""
    print("💸 Starting Transaction Agent")
    
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
        
        # Create transaction agent
        agent_executor = await create_transaction_agent(coral_tools)
        executor = MockTransactionExecutor()
        
        print("🎯 Transaction agent ready!")
        
        # Main transaction loop
        while True:
            try:
                # Listen for transaction requests
                await agent_executor.ainvoke({
                    "input": "Listen for validated tips and execute transactions",
                    "agent_scratchpad": []
                })
                await asyncio.sleep(5)
                
            except Exception as e:
                print(f"❌ Transaction error: {e}")
                logger.error(f"Transaction error: {e}")
                await asyncio.sleep(10)
                
    except Exception as e:
        print(f"💥 Fatal error in transaction agent: {e}")
        logger.error(f"Fatal error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())