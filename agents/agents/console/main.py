#!/usr/bin/env python3
"""
Console Interface Agent
Handles user input and coordinates other agents
"""

import asyncio
import os
import re
import json
import logging
from datetime import datetime
from typing import Dict, Any, Optional
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

class ConsoleTipInterface:
    """Console interface for tip command processing"""
    
    def __init__(self):
        self.balance = float(os.getenv('INITIAL_BALANCE', '100.0'))
        self.tip_pattern = re.compile(r'/tip\s+@(\S+)\s+([\d.]+)\s+SOL\s*(.*)', re.IGNORECASE)
        self.transaction_history = []
        
    def parse_tip_command(self, command: str) -> Optional[Dict[str, Any]]:
        """Parse console tip command"""
        match = self.tip_pattern.search(command)
        if not match:
            return None
            
        return {
            'recipient': match.group(1),
            'amount': float(match.group(2)),
            'message': match.group(3).strip(),
            'timestamp': datetime.utcnow().isoformat(),
            'platform': 'console',
            'author_id': 'console_user'
        }
    
    def display_balance(self) -> str:
        """Display current balance"""
        return f"💰 Current Balance: {self.balance:.4f} SOL"
    
    def display_history(self) -> str:
        """Display recent transaction history"""
        if not self.transaction_history:
            return "📜 No transactions yet"
        
        history = "📜 Recent Transactions:\n"
        for tx in self.transaction_history[-5:]:
            history += f"  • {tx['amount']:.4f} SOL → @{tx['recipient']} ({tx['timestamp']})\n"
        
        return history

def load_config() -> Dict[str, Any]:
    """Load configuration from environment variables"""
    config = {
        "coral_connection_url": os.getenv("CORAL_CONNECTION_URL", "http://localhost:5555"),
        "agent_id": os.getenv("CONSOLE_AGENT_ID", "console"),
        "model_name": os.getenv("MODEL_NAME", "mistral-small"),
        "model_provider": os.getenv("MODEL_PROVIDER", "mistral"),
        "api_key": os.getenv("MISTRAL_API_KEY"),
        "model_temperature": float(os.getenv("MODEL_TEMPERATURE", "0.3")),
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

async def create_console_agent(coral_tools) -> AgentExecutor:
    """Create console interface agent with Mistral AI"""
    
    coral_tools_description = get_tools_description(coral_tools)
    
    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            f"""You are a console interface agent for a crypto tipping system.

Your responsibilities:
1. Parse user tip commands: /tip @recipient amount SOL message
2. Coordinate with other agents through Coral Protocol
3. Display results to the user
4. Handle user queries about balance and history

Available Coral tools: {coral_tools_description}

Process flow for tip commands:
1. Parse the command (recipient, amount, message)
2. Create thread with validation agent
3. Send tip data for validation
4. Wait for validation result
5. If valid, create thread with transaction agent
6. Send validated tip data for execution
7. Wait for transaction result
8. Create thread with notification agent
9. Send transaction result for notification
10. Display final result to user

For balance queries: Display current balance
For history queries: Display recent transactions

Always use proper thread management and agent communication.
"""
        ),
        ("human", "{input}"),
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
    """Main console interface loop"""
    print(" Coral Protocol + Mistral AI Tipping System")
    print("=" * 50)
    print("Commands:")
    print("  /tip @recipient amount SOL message")
    print("  /balance")
    print("  /history")
    print("  /help")
    print("  /quit")
    print("=" * 50)
    
    try:
        # Load configuration
        config = load_config()
        
        # Connect to Coral Server
        print(" Connecting to Coral Server...")
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
        
        # Create console agent
        agent_executor = await create_console_agent(coral_tools)
        interface = ConsoleTipInterface()
        
        print("🎯 Console interface ready!")
        print("💡 Type /help for available commands")
        
        # Main console loop
        while True:
            try:
                command = input("\n💬 Enter command: ").strip()
                
                if command.lower() in ['quit', 'exit', 'q']:
                    print("👋 Goodbye!")
                    break
                
                elif command.lower() == '/help':
                    print("""
📚 Available Commands:
  /tip @recipient amount SOL message  - Send a tip
  /balance                            - Check your balance
  /history                            - View transaction history
  /help                               - Show this help
  /quit                               - Exit the system
                    """)
                
                elif command.lower() == '/balance':
                    print(interface.display_balance())
                
                elif command.lower() == '/history':
                    print(interface.display_history())
                
                elif command.startswith('/tip'):
                    # Parse tip command
                    tip_data = interface.parse_tip_command(command)
                    
                    if not tip_data:
                        print("❌ Invalid tip command format")
                        print("💡 Use: /tip @recipient amount SOL message")
                        continue
                    
                    print(f" Processing tip: {tip_data['amount']} SOL → @{tip_data['recipient']}")
                    
                    # Process through Coral Protocol agents
                    try:
                        result = await agent_executor.ainvoke({
                            "input": f"Process tip command: {command}",
                            "agent_scratchpad": []
                        })
                        
                        output = result.get('output', 'Processing...')
                        print(f"📋 Result: {output}")
                        
                        # Update local state if successful
                        if "success" in output.lower() or "sent" in output.lower():
                            interface.transaction_history.append({
                                'amount': tip_data['amount'],
                                'recipient': tip_data['recipient'],
                                'timestamp': tip_data['timestamp']
                            })
                            interface.balance -= tip_data['amount']
                        
                    except Exception as e:
                        print(f"❌ Error processing tip: {e}")
                
                else:
                    print("❌ Unknown command. Type /help for available commands")
                    
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
                logger.error(f"Console error: {e}")
                
    except Exception as e:
        print(f"💥 Fatal error: {e}")
        logger.error(f"Fatal error: {e}")
        raise

if __name__ == "__main__":
    asyncio.run(main())